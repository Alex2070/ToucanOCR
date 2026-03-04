import base64
from zai import ZhipuAiClient
import os
from pathlib import Path
from pdf2md.merge_md import merge_markdown_files
import shutil
from pypdf import PdfReader, PdfWriter
from pdf2md.md_context import MdContext
import tkinter as tk



class MdConverter:

    def __init__(self,context:MdContext=None):
        self.context=context
    
    def small_file_to_raw_md(self,file_path,output_folder_path):
        api_key = self.context.api_key.get("glm_api_key",None)
        if not api_key:
            print("Please set api key first")
            tk.messagebox.showerror("Error", "Please set api key first")
            return
        client = ZhipuAiClient(api_key=api_key)

        file_path=Path(file_path)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.svg','.pdf']:
            print(f"Unsupported image format: {file_path.suffix}")
            raise Exception(f"Unsupported image format: {file_path.suffix}")

        # 检查文件大小
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
        if file_path.suffix.lower() == '.pdf':
            if file_size > 50:
                print(f"PDF文件过大: {file_size:.2f}MB (限制: 50MB)")
                raise Exception(f"PDF文件过大: {file_size:.2f}MB (限制: 50MB)")
        else:  # 图片文件
            if file_size > 10:
                print(f"图片文件过大: {file_size:.2f}MB (限制: 10MB)")
                raise Exception(f"图片文件过大: {file_size:.2f}MB (限制: 10MB)")
            
        output_folder_path = Path(output_folder_path)
        if not os.path.exists(output_folder_path):
            os.makedirs(output_folder_path)
        
        with open(file_path, "rb") as f:
            b64date=base64.b64encode(f.read()).decode("utf-8")
        
        if file_path.suffix.lower() == '.pdf':
            response = client.layout_parsing.create(
                model="glm-ocr",
                file=f"data:application/pdf;base64,{b64date}",
                return_crop_images=True,
            )
        else:
            response = client.layout_parsing.create(
                model="glm-ocr",
                file=f"data:image/{file_path.suffix[1:]};base64,{b64date}",
                return_crop_images=True,
            )
        token_usage=response.usage.total_tokens+self.context.config.get("token_usage",0)
        self.context.config['token_usage']=token_usage
        output_filename = output_folder_path / f"{file_path.stem}.md"
        with open(output_filename, "w",encoding="utf-8") as f:        
            f.write(response.md_results)
        res={}
        res['file_path']=output_filename
        res['token_usage']=response.usage.total_tokens
        return res
    
    def large_pdf_to_raw_md(self, file_path, output_folder_path):
        api_key = self.context.api_key.get("glm_api_key",None)
        if not api_key:
            print("Please set api key first")
            tk.messagebox.showerror("Error", "Please set api key first")
            return
        file_path=Path(file_path)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() != '.pdf':
            print(f"Unsupported file format: {file_path.suffix}")
            raise Exception(f"Unsupported file format: {file_path.suffix}")

        output_folder_path = Path(output_folder_path)
        if not os.path.exists(output_folder_path):
            os.makedirs(output_folder_path)
        
        temp_path=output_folder_path/f"{file_path.stem}_temp"
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        files=self.split_pdf(input_file_path=file_path, output_folder_path=temp_path)
        mds=[]
        for file in files:
            md=self.small_file_to_raw_md(file,temp_path)
            mds.append(md)
        md_paths=[md['file_path'] for md in mds if md]
        sum_token_usage=sum(md['token_usage'] for md in mds)
        merged_md_path= output_folder_path / f"{file_path.stem}.md"
        merge_markdown_files(md_paths, merged_md_path, separator="\n\n")
        shutil.rmtree(temp_path)
        return {'file_path':merged_md_path, 'token_usage':sum_token_usage}

    def split_pdf(self, input_file_path, output_folder_path,max_pages_per_file=100,max_file_size_mb=50):
        
        input_file_path=Path(input_file_path)
        if not os.path.exists(input_file_path):
            print(f"File not found: {input_file_path}")
            raise FileNotFoundError(f"File not found: {input_file_path}")
        
        if input_file_path.suffix.lower() != '.pdf':
            print(f"Unsupported file format: {input_file_path.suffix}")
            raise Exception(f"Unsupported file format: {input_file_path.suffix}")

        output_folder_path = Path(output_folder_path)
        if not os.path.exists(output_folder_path):
            os.makedirs(output_folder_path)

        # 打开原始PDF文件
        with open(input_file_path, 'rb') as infile:
            reader = PdfReader(infile)
            total_pages = len(reader.pages)
            filesize=os.path.getsize(input_file_path) / (1024 * 1024)  # 获取文件大小，单位为MB
            num_files_by_size = int(filesize // max_file_size_mb) + 1  # 根据文件大小计算需要分割的文件数量
            num_files_by_pages = (total_pages + max_pages_per_file - 1) // max_pages_per_file  # 根据页数计算需要分割的文件数量
            if num_files_by_size > num_files_by_pages:
                max_pages_per_file = (total_pages + num_files_by_size - 1) // num_files_by_size  # 调整每个文件的页数以满足文件大小限制
   
            # 分割PDF
            output_files = []
            for start_page in range(0, total_pages, max_pages_per_file):
                writer = PdfWriter()
                end_page = min(start_page + max_pages_per_file, total_pages)

                for page in range(start_page, end_page):
                    writer.add_page(reader.pages[page])

                output_filename = output_folder_path / f"{input_file_path.stem}_{start_page // max_pages_per_file + 1}.pdf"
                with open(output_filename, 'wb') as outfile:
                    writer.write(outfile)
                output_files.append(output_filename)
        return output_files






