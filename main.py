from pdf2md import *
import os
import tkinter as tk
from tkinter.ttk import Notebook
from tkinter import filedialog
import threading
from pathlib import Path
import webbrowser
import json
import time
import shutil

API_KEY_FILE = Path.home() / ".ToucanOCR_key.json"
CONFIG_FILE = Path.cwd() / "config.json"
MD_CONTEXT=None


def open_url(url):
   webbrowser.open_new_tab(url)


def thread_it(func):
	t = threading.Thread(target=func)
	t.daemon=True
	t.start()


def refresh_token_usage():
	global MD_CONTEXT
	token_usage=MD_CONTEXT.config.get('token_usage',0)
	if token_usage > 1000*1000*1000:
		token_usage_label.config(text=f'累计使用token数量：{token_usage/(1000*1000*1000):.2f}B')
	elif token_usage > 1000*1000:
		token_usage_label.config(text=f'累计使用token数量：{token_usage/(1000*1000):.2f}M')
	elif token_usage > 1000:
		token_usage_label.config(text=f'累计使用token数量：{token_usage/(1000):.2f}K')
	else:
		token_usage_label.config(text=f'累计使用token数量：{token_usage}')


def set_api_key_dialog():
# 创建对话框窗口
	dialog = tk.Toplevel(root)
	dialog.title("设置GLM API Key")
	dialog.geometry("400x200")
	
	# 添加标签和输入框
	tk.Label(dialog, text="请输入GLM-OCR API Key:").pack(pady=(10, 5))
	key_entry = tk.Entry(dialog, width=40, show="*")  # show="*"使输入内容显示为星号
	key_entry.pack(pady=5)

	label_frame = tk.Frame(dialog)
	label_frame.pack(pady=10)
	tk.Label(label_frame, text="api key注册链接：").pack(side=tk.LEFT, padx=5)
	link = tk.Label(label_frame, text="https://bigmodel.cn/", fg="blue")
	link.pack(side=tk.LEFT, padx=5)
	link.bind("<Button-1>", lambda e: open_url("https://bigmodel.cn/"))

	# 添加确认和取消按钮
	def save_key():
		key = key_entry.get()
		if not key:
			tk.messagebox.showwarning("警告", "请输入有效的API Key")
			dialog.destroy()
			return
		MD_CONTEXT.api_key['glm_api_key']= key
		MD_CONTEXT.save_api_key()
		dialog.destroy()
		tk.messagebox.showinfo("提示", "API Key已保存")
	
	button_frame = tk.Frame(dialog)
	button_frame.pack(pady=10)
	tk.Button(button_frame, text="确认", command=save_key).pack(side=tk.LEFT, padx=5)
	tk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

	

# 回调：弹出文件/目录选择并回填对应 Entry
def single_file_select():
	path = filedialog.askopenfilename(title='选择 PDF 或图片', filetypes=[('PDF或图片','*.pdf;*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp;*.svg')])
	if path:
		single_select_entry.config(state='normal')
		single_select_entry.delete(0, tk.END)
		single_select_entry.insert(0, path)
		single_select_entry.config(state='disabled')

def folder_select(entry,title):
	path = filedialog.askdirectory(title=title)
	if path:
		entry.config(state='normal')
		entry.delete(0, tk.END)
		entry.insert(0, path)
		entry.config(state='disabled')


def md_file_select():
	path = filedialog.askopenfilename(title='选择 md 文件', filetypes=[('md文件','*.md')])
	if path:
		translator_select_entry.config(state='normal')
		translator_select_entry.delete(0, tk.END)
		translator_select_entry.insert(0, path)
		translator_select_entry.config(state='disabled')


def single_convert():
	global MD_CONTEXT
	api_key = MD_CONTEXT.api_key.get("glm_api_key",None)
	if not api_key:
		print("Please set api key first")
		tk.messagebox.showerror("Error", "Please set api key first")
		return
	file_path = single_select_entry.get()
	out_path = single_out_entry.get()
	if not os.path.exists(file_path):
		tk.messagebox.showerror('错误', '请选择有效的文件')
		return
	if not os.path.exists(out_path):
		tk.messagebox.showerror('错误', '请选择有效的输出目录')
		return
	file_dir, file_name = os.path.split(file_path)
	file_base, file_ext = os.path.splitext(file_name)
	file_ext = file_ext.lower()
	if file_ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.svg','.pdf']:
		tk.messagebox.showerror('错误', '只支持图片文件和PDF文件')
		return
	show_message.config(text='开始转换,可能需要几分钟时间,请耐心等待...')
	start_time = time.time()
	single_convert_button.config(state='disabled')
	show_message.config(text='正在处理{}...'.format(file_name))
	try:
		if file_ext == '.pdf':
			res=md_converter.large_pdf_to_raw_md(file_path, out_path)
		else:
			res=md_converter.small_file_to_raw_md(file_path, out_path)
	except Exception as e:
		print(e)
		show_message.config(text='转换失败')
		single_convert_button.config(state='normal')
		tk.messagebox.showerror("Error", str(e))
		return
	convert_image_local(res['file_path'])
	single_convert_button.config(state='normal')
	show_message.config(text=f'{file_name}转换完成, 用时{int(time.time()-start_time)}秒，共使用token数量：{res["token_usage"]}')
	refresh_token_usage()


def folder_convert():
	global MD_CONTEXT
	api_key = MD_CONTEXT.api_key.get("glm_api_key",None)
	if not api_key:
		print("Please set api key first")
		tk.messagebox.showerror("Error", "Please set api key first")
		return
	folder_path = folder_select_entry.get()
	if not os.path.exists(folder_path):
		tk.messagebox.showerror('错误', '请选择有效的文件夹')
		return
	folder_path=Path(folder_path)
	out_path = folder_out_entry.get()
	if not os.path.exists(out_path):
		tk.messagebox.showerror('错误', '请选择有效的输出目录')
		return
	out_path=Path(out_path)
	folder_convert_button.config(state='disabled')
	show_message.config(text='开始转换...可能需要几分钟时间，请耐心等待')
	start_time=time.time()
	files=[Path(os.path.join(folder_path, file)) for file in os.listdir(folder_path) if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.svg','.pdf'))]
	try:
		if var.get() == 1:
			temp_path=out_path/'temp'
			os.makedirs(temp_path, exist_ok=True)
			mds=[]
			for file in files:
				show_message.config(text='正在处理{}...'.format(file.name))
				if file.suffix == '.pdf':
					res=md_converter.large_pdf_to_raw_md(file, temp_path)
				else:
					res=md_converter.small_file_to_raw_md(file, temp_path)
				mds.append(res)		
			paths=[md['file_path'] for md in mds]
			paths.sort()
			res=merge_markdown_files(paths, out_path/'output.md')
			convert_image_local(res)
			tokens=sum([md['token_usage'] for md in mds])
			shutil.rmtree(temp_path)

		else:
			mds=[]
			for file in files:
				show_message.config(text='正在处理{}...'.format(file.name))
				if file.suffix == '.pdf':
					res=md_converter.large_pdf_to_raw_md(file, out_path)
				else:
					res=md_converter.small_file_to_raw_md(file, out_path)
				convert_image_local(res['file_path'])
				mds.append(res)
			tokens=sum([md['token_usage'] for md in mds])
	except Exception as e:
		print(e)
		show_message.config(text='转换失败')
		folder_convert_button.config(state='normal')
		tk.messagebox.showerror("Error", str(e))
		return
	folder_convert_button.config(state='normal')
	show_message.config(text=f'转换完成, 用时{time.time()-start_time}秒，共使用token数量：{tokens}')
	refresh_token_usage()

def translator_convert():
	global MD_CONTEXT
	api_key = MD_CONTEXT.api_key.get("glm_api_key",None)
	if not api_key:
		print("Please set api key first")
		tk.messagebox.showerror("Error", "Please set api key first")
		return
	md_file_path = translator_select_entry.get()
	if not os.path.exists(md_file_path):
		tk.messagebox.showerror('错误', '请选择有效的md文件')
		return
	md_file_path=Path(md_file_path)
	out_path=md_file_path.parent
	translator_convert_button.config(state='disabled')
	show_message.config(text='开始翻译...可能需要几分钟时间，请耐心等待')
	start_time=time.time()
	try:
		res=translator.translate_md_file(md_file_path, out_path)
	except Exception as e:
		print(e)
		show_message.config(text='翻译失败')
		translator_convert_button.config(state='normal')
		tk.messagebox.showerror("Error", str(e))
	translator_convert_button.config(state='normal')
	show_message.config(text=f'翻译完成, 耗时：{int(time.time()-start_time)}秒, 共使用token数量：{res['token_usage']}')
	refresh_token_usage()
	
def on_closing():
	MD_CONTEXT.save_config()
	root.destroy()	

	


if __name__ == '__main__':
	MD_CONTEXT = MdContext(API_KEY_FILE,CONFIG_FILE)
	translator = Translator(MD_CONTEXT)
	md_converter= MdConverter(MD_CONTEXT)
	root = tk.Tk()
	root.geometry('600x400')
	root.title('ToucanOCR v1.1.0')
	root.iconbitmap('ToucanOCR.ico')

	key_row = tk.Frame(root)
	key_row.pack(fill=tk.X)
	tk.Button(key_row, text='设置GLM API Key',command=set_api_key_dialog).pack(side=tk.LEFT, padx=(10,5), pady=5)

	token_usage_label = tk.Label(key_row, text=f'累计使用token数量：{MD_CONTEXT.config.get('token_usage',0)}')
	token_usage_label.pack(side=tk.RIGHT, padx=(0,10), pady=5)
	refresh_token_usage()


	notebook = Notebook(root)

	# 单文件转md的UI===========================================================================

	single_file_frame = tk.Frame()
	single_file_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

	tk.Label(single_file_frame, text='文件路径：').pack(anchor='w', padx=10, pady=(5,0))

	single_select_row = tk.Frame(single_file_frame)
	single_select_row.pack(fill=tk.X)

	single_select_entry = tk.Entry(single_select_row,width=30,state='disabled')
	single_select_entry.pack(side=tk.LEFT, padx=(10,5), pady=5, fill=tk.X, expand=True)

	tk.Button(single_select_row, text='选择文件', command=single_file_select).pack(side=tk.LEFT, padx=(0,10), pady=5)

	tk.Label(single_file_frame, text='输出路径：').pack(anchor='w', padx=10, pady=(5,0))

	single_out_row = tk.Frame(single_file_frame)
	single_out_row.pack(fill=tk.X)

	single_out_entry = tk.Entry(single_out_row, width=30,state='disabled')
	single_out_entry.pack(side=tk.LEFT, padx=(10,5), pady=5, fill=tk.X, expand=True)

	tk.Button(single_out_row, text='选择文件夹', command=lambda: folder_select(single_out_entry, '选择输出目录')).pack(side=tk.LEFT, padx=(0,10), pady=5)
	
	single_convert_button=tk.Button(single_file_frame, text='开始转换',command=(lambda:thread_it(single_convert)))
	single_convert_button.pack(padx=10, pady=10)


	# 多文件转md的UI======================================================================

	folder2md_frame = tk.Frame()
	
	tk.Label(folder2md_frame, text='文件夹路径：').pack(anchor='w', padx=10, pady=(5,0))
	folder_select_row = tk.Frame(folder2md_frame)
	folder_select_row.pack(fill=tk.X)

	folder_select_entry = tk.Entry(folder_select_row,width=30,state='disabled')
	folder_select_entry.pack(side=tk.LEFT, padx=(10,5), pady=5, fill=tk.X, expand=True)
	
	tk.Button(folder_select_row, text='选择文件夹', command=lambda: folder_select(folder_select_entry, '选择图片集文件夹')).pack(side=tk.LEFT, padx=(0,10), pady=5)

	tk.Label(folder2md_frame, text='输出路径：').pack(anchor='w', padx=10, pady=(5,0))

	folder_out_row = tk.Frame(folder2md_frame)
	folder_out_row.pack(fill=tk.X)

	folder_out_entry = tk.Entry(folder_out_row, width=30,state='disabled')
	folder_out_entry.pack(side=tk.LEFT, padx=(10,5), pady=5, fill=tk.X, expand=True)

	tk.Button(folder_out_row, text='选择文件夹', command=lambda: folder_select(folder_out_entry, '选择输出目录')).pack(side=tk.LEFT, padx=(0,10), pady=5)
	
	var = tk.IntVar()
	checkbox_frame = tk.Frame(folder2md_frame)
	checkbox_frame.pack(fill=tk.X)	

	checkbox=tk.Checkbutton(checkbox_frame, text="合并为一个文件", variable=var, onvalue=1, offvalue=0,)
	checkbox.pack(side=tk.LEFT,padx=0, pady=0)

	folder_convert_button=tk.Button(folder2md_frame, text='开始转换',command=(lambda:thread_it(folder_convert)))
	folder_convert_button.pack(padx=10, pady=10)



	#md翻译UI======================================================================

	translator_frame = tk.Frame()

	tk.Label(translator_frame, text='md文件路径：').pack(anchor='w', padx=10, pady=(5,0))

	translator_select_row = tk.Frame(translator_frame)
	translator_select_row.pack(fill=tk.X)

	translator_select_entry = tk.Entry(translator_select_row,width=30,state='disabled')
	translator_select_entry.pack(side=tk.LEFT, padx=(10,5), pady=5, fill=tk.X, expand=True)

	tk.Button(translator_select_row, text='选择md文件', command=md_file_select).pack(side=tk.LEFT, padx=(0,10), pady=5)
	translator_convert_button=tk.Button(translator_frame, text='开始翻译',command=(lambda:thread_it(translator_convert)))
	translator_convert_button.pack(padx=10, pady=10)


	# 将三个功能的Frame添加到Notebook中=================================================
	notebook.add(single_file_frame, text='单个文件转md')
	notebook.add(folder2md_frame, text='多个文件转md')
	notebook.add(translator_frame, text='翻译md文件')
	notebook.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

	#底部信息显示UI======================================================================
	show_message=tk.Label(root, text='欢迎使用ToucanOCR')
	show_message.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

	root.protocol("WM_DELETE_WINDOW", on_closing)
	root.mainloop()



