from zai import ZhipuAiClient
import os
import re
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from pdf2md.md_context import MdContext

class Translator:
    def __init__(self,context: MdContext=None):
        self.context=context

    def translate_text(self,text: str) -> str:
        api_key = self.context.api_key.get('glm_api_key', None)
        if not api_key:
            print("未设置API密钥")
            raise ValueError("未设置API密钥")
        client = ZhipuAiClient(api_key=api_key)
        try:
            default_msg=[
            {"role": "system", "content": "你是一个翻译领域专家"},
            {"role": "user", "content": "将以下markdown文本中的标题、以“###”、“##”开头的行和正文翻译成中文,内容要忠实于原文,表格、引用文献、公式、代码块不用翻译，特别注意保持markdown格式不变，直接输出翻译完的md文本，不要添加额外的东西"},
            {"role": "assistant", "content": "当然，请给出要翻译的markdown文本"}
            ]
            msg=self.context.config.get('translator_msg',default_msg)+[{"role": "user", "content": text}]

            response = client.chat.asyncCompletions.create(
            model=self.context.config.get('translator_model',"glm-4-flashx-250414"),
            messages=msg,        
            do_sample=False,            # 禁用随机采样
            )
            task_id = response.id
            waiting_time = 0
            while True:
                response = client.chat.asyncCompletions.retrieve_completion_result(id=task_id)

                # 处理状态: PROCESSING (处理中)、SUCCESS (成功)、FAIL (失败)
                if response.task_status == "SUCCESS":
                    return {'content':response.choices[0].message.content,'total_tokens':response.usage.total_tokens}
                elif response.task_status == "FAIL":
                    print(f"任务失败: {response.error_message}")
                    return 
                time.sleep(1)
                waiting_time += 1
                if waiting_time > 300:  # 等待300秒后放弃
                    print("等待超时，放弃翻译")
                    return 
        except Exception as e:
            print(f"翻译失败: {e}")
            return 


    def translate_md_file(self,input_file: str, output_folder_path: str):
        input_file=Path(input_file)
        output_folder_path=Path(output_folder_path)
        if not os.path.exists(input_file):
            print(f"File not found: {input_file}")
            raise FileNotFoundError(f"File not found: {input_file}")
        mds = self.split_md_file(input_file)
        
        # 使用线程池进行并行翻译，保持顺序
        translated_results = [None] * len(mds)  # 预分配结果列表
        
        def translate_with_index(index, text):
            """翻译函数，返回索引和翻译结果"""
            return index, self.translate_text(text)
        
        # 使用10个线程进行翻译
        workers=self.context.config.get('translator_workers',100)
        if workers<1:
            workers=1
        elif workers>100:
            workers=100
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有任务
            futures = {executor.submit(translate_with_index, i, md): i for i, md in enumerate(mds)}
            # 收集结果，按原始顺序存储
            for future in as_completed(futures):
                index, translated_md = future.result()
                if translated_md:
                    translated_results[index] = translated_md       
        # 按顺序拼接结果
        res = ""
        for translated_md in translated_results:
            if translated_md:
                res += translated_md['content']
                res += '\n\n'
        tokens = sum([r['total_tokens'] for r in translated_results if r])
        token_usage =self.context.config.get('token_usage',0)+tokens
        self.context.config['token_usage']=token_usage
        print(f"翻译完成，tokens用量: {tokens}")
        with open(output_folder_path/f"{input_file.stem}_translated.md", 'w', encoding="utf-8") as f:
            f.write(res)
        return {'file_path':output_folder_path,'token_usage':tokens}

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, int(len(text) / 4))

    def split_md_file(self, input_file: str, max_tokens: int = 3000) -> List[str]:
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_file}")
        text = input_path.read_text(encoding='utf-8')

        lines = text.splitlines(keepends=True)
        sections: List[str] = []
        current = ''
        heading_re = re.compile(r'^\s*#{1,6}\s+')
        for line in lines:
            if heading_re.match(line):
                if current:
                    sections.append(current)
                current = line
            else:
                current += line
        if current:
            sections.append(current)

        if len(sections) <= 1:
            sections = [p for p in re.split(r'\n{2,}', text) if p.strip()]

        chunks: List[str] = []
        current_chunk = ''

        for sec in sections:
            sec = sec.rstrip()
            sec_tokens = self._estimate_tokens(sec)
            if sec_tokens > max_tokens:
                parts = [p for p in re.split(r'\n{2,}', sec) if p.strip()]
                for part in parts:
                    part = part.rstrip()
                    part_tokens = self._estimate_tokens(part)
                    if part_tokens > max_tokens:
                        chunk_chars = max(int(max_tokens * 4), 1024)
                        start = 0
                        while start < len(part):
                            md_slice = part[start:start + chunk_chars]
                            if current_chunk and self._estimate_tokens(current_chunk) + self._estimate_tokens(md_slice) <= max_tokens:
                                current_chunk += '\n\n' + md_slice
                            else:
                                if current_chunk:
                                    chunks.append(current_chunk)
                                current_chunk = md_slice
                            start += chunk_chars
                    else:
                        if current_chunk and self._estimate_tokens(current_chunk) + part_tokens <= max_tokens:
                            current_chunk += '\n\n' + part
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = part
            else:
                if current_chunk and self._estimate_tokens(current_chunk) + sec_tokens <= max_tokens:
                    current_chunk += '\n\n' + sec
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sec

        if current_chunk:
            chunks.append(current_chunk)

        chunks = [c.strip() for c in chunks if c.strip()]
        return chunks
    

    



        