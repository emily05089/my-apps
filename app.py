import os
import re
import io
import fitz
from PIL import Image
from flask import Flask, request, render_template_string
# 引入百度 OCR SDK
from aip import AipOcr

app = Flask(__name__)

# ==================== ⚠️ 请在这里填入你的百度 API 凭证 ====================
APP_ID = '123874873'
API_KEY = 'je80X5GVDpDMs1tC6ykZAyN3'
SECRET_KEY = 'FMLU6MzUs21ujF7YlWFIWCFv0nkeID7w'
# ========================================================================

# 初始化百度 OCR 客户端
client = AipOcr(APP_ID, API_KEY, SECRET_KEY)

# 把图片读成字节流，发给百度识别
def parse_image_to_text_baidu(img):
    try:
        # 将 PIL 图片对象转成字节流
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        image_bytes = img_byte_arr.getvalue()
        
        # 调用百度高精度接口 (basicAccurate 极高精度)
        options = {"language_type": "CHN_ENG", "detect_direction": "true"}
        result = client.basicAccurate(image_bytes, options)
        
        # 拼合百度的识别结果
        text = ""
        if 'words_result' in result:
            for item in result['words_result']:
                text += item['words'] + "\n"
        return text
    except Exception as e:
        return "" # 如果百度识别失败，返回空字符串

# 核心逻辑 (正则提取与倍数展开 - 不变)
def parse_format(raw_text):
    output_lines = []
    lines = raw_text.split('\n')
    current_reds, current_blues, current_dan, current_tuo = [], [], [], []
    multiplier = 1
    for line in lines:
        red_match = re.search(r'[红R][球复]?[:：]\s*(.+)', line)
        if red_match:
            nums = re.findall(r'\b(\d{1,2})\b', red_match.group(1))
            if nums: current_reds = nums

        blue_match = re.search(r'[蓝B][球复单]?[:：]\s*(.+)', line)
        if blue_match:
            nums = re.findall(r'\b(\d{1,2})\b', blue_match.group(1))
            if nums: current_blues = nums

        m_match = re.search(r'[\[\(（]\s*(\d+)\s*[倍]\s*[\]\)）]', line) or re.search(r'倍数[:：]\s*(\d+)', line)
        if m_match:
            multiplier = int(m_match.group(1))

        dan_match = re.search(r'红胆[:：]\s*(.*?)(?=\s*红拖|\s*蓝球|\s*$)', line)
        if dan_match:
            current_dan = re.findall(r'\b(\d{1,2})\b', dan_match.group(1))
        tuo_match = re.search(r'红拖[:：]\s*(.*?)(?=\s*蓝球|\s*$)', line)
        if tuo_match:
            current_tuo = re.findall(r'\b(\d{1,2})\b', tuo_match.group(1))

        if current_reds and current_blues:
            red_str = ",".join(current_reds)
            for _ in range(max(1, multiplier)):
                for blue in current_blues:
                    output_lines.append(f"{red_str}-{blue}")
            current_blues = []
            multiplier = 1

        if current_dan and current_tuo and current_blues:
            dan_str = f"胆:{','.join(current_dan)}，拖:{','.join(current_tuo)}"
            for _ in range(max(1, multiplier)):
                for blue in current_blues:
                    output_lines.append(f"{dan_str}-{blue}")
            current_dan, current_tuo, current_blues = [], [], []
            multiplier = 1
    return "\n".join(output_lines)


# ==================== 网页 UI (和上一版一样) ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>双色球多图识别(百度高精度)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 15px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; }
        h1 { font-size: 22px; text-align: center; color: #333; }
        .upload-actions { display: flex; gap: 10px; margin: 15px 0; flex-wrap: wrap; }
        .btn { border: none; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: bold; color: white; cursor: pointer; }
        .btn-add { background: #007bff; flex: 1; }
        .btn-start { background: #e60012; flex: 2; }
        .btn-clean { background: #6c757d; flex: 1; }
        .btn:active { opacity: 0.8; }
        .file-input { display: none; }
        .file-list { display: flex; flex-direction: column; gap: 10px; margin: 15px 0; max-height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 8px; }
        .file-item { display: flex; align-items: center; justify-content: space-between; padding: 8px; background: #fafafa; border: 1px solid #ddd; border-radius: 6px; }
        .file-preview { display: flex; align-items: center; gap: 10px; overflow: hidden; }
        .file-preview img, .file-preview .pdf-icon { width: 40px; height: 40px; border-radius: 4px; object-fit: cover; background: #eee; }
        .file-name { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
        .btn-del { background: #dc3545; padding: 4px 8px; font-size: 12px; }
        .loading { display: none; text-align: center; margin: 10px 0; color: #e60012; font-weight: bold; }
        textarea { width: 100%; height: 40vh; font-size: 14px; padding: 10px; border: 1px solid #ccc; border-radius: 8px; box-sizing: border-box; margin-top: 15px; resize: vertical; }
        .copy-btn { background: #28a745; margin-top: 10px; width: 100%; padding: 12px; }
        #error-message { display: none; color: red; margin-top: 10px; font-weight: bold; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🍀 双色球识别 (百度高精度版)</h1>
        <div class="upload-actions">
            <button class="btn btn-add" onclick="document.getElementById('fileInput').click()">➕ 添加图片/PDF</button>
            <button class="btn btn-clean" onclick="clearList()">🗑️ 清空列表</button>
            <button class="btn btn-start" onclick="uploadFiles()">🚀 识别全部</button>
        </div>
        <input type="file" id="fileInput" class="file-input" accept=".pdf,.jpg,.png,.jpeg" multiple onchange="handleFiles(this.files)">
        <div id="fileListContainer" class="file-list"><div style="color:#999; text-align:center; padding:10px;">暂无文件</div></div>
        <div id="loading" class="loading">⏳ 百度正在识别，请稍候（大概几秒到十几秒）...</div>
        <div id="error-message"></div>
        <div>
            <textarea id="result" placeholder="识别结果将在这里显示，长按即可全选复制">{{ result }}</textarea>
            <button class="btn copy-btn" onclick="copyText()">📋 一键复制全部结果</button>
        </div>
    </div>
    <script>
        let selectedFiles = [];
        function handleFiles(files) {
            const listContainer = document.getElementById('fileListContainer');
            if(files.length === 0) return;
            for(let i=0; i<files.length; i++) selectedFiles.push(files[i]);
            renderList();
            document.getElementById('fileInput').value = '';
        }
        function renderList() {
            const listContainer = document.getElementById('fileListContainer');
            listContainer.innerHTML = '';
            if(selectedFiles.length === 0){ listContainer.innerHTML = '<div style="color:#999; text-align:center; padding:10px;">暂无文件</div>'; return; }
            for(let i=0; i<selectedFiles.length; i++){
                const file = selectedFiles[i];
                const item = document.createElement('div'); item.className = 'file-item';
                const previewHtml = file.type.startsWith('image/') ? `<img src="${URL.createObjectURL(file)}">` : `<div class="pdf-icon">📄</div>`;
                item.innerHTML = `
                    <div class="file-preview">${previewHtml}<span class="file-name">${file.name.length > 15 ? file.name.substring(0,12)+'...' : file.name}</span></div>
                    <button class="btn btn-del" onclick="removeFile(${i})">删除</button>
                `;
                listContainer.appendChild(item);
            }
        }
        function removeFile(index) { selectedFiles.splice(index, 1); renderList(); document.getElementById('result').value = ''; document.getElementById('error-message').style.display = 'none'; }
        function clearList() { selectedFiles = []; document.getElementById('fileInput').value = ''; renderList(); document.getElementById('result').value = ''; document.getElementById('error-message').style.display = 'none'; }
        async function uploadFiles() {
            if(selectedFiles.length === 0){ alert("请至少添加一张图片或一个PDF文件！"); return; }
            document.getElementById('loading').style.display = 'block'; document.getElementById('error-message').style.display = 'none';
            const btnStart = document.querySelector('.btn-start'); btnStart.disabled = true;
            const formData = new FormData(); for(let i=0; i<selectedFiles.length; i++) formData.append('files', selectedFiles[i]);
            try {
                const response = await fetch('/', { method: 'POST', body: formData });
                const textResult = await response.text();
                document.getElementById('result').value = textResult;
            } catch (error) {
                document.getElementById('error-message').innerText = "识别出错，请检查下方终端是否有报错！";
                document.getElementById('error-message').style.display = 'block';
            } finally {
                document.getElementById('loading').style.display = 'none'; btnStart.disabled = false;
            }
        }
        function copyText() { var copyText = document.getElementById("result"); copyText.select(); copyText.setSelectionRange(0, 99999); document.execCommand("copy"); alert("已成功复制全部结果！"); }
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        full_result = []
        for file in uploaded_files:
            file_name = file.filename.lower()
            try:
                if file_name.endswith('.pdf'):
                    pdf_doc = fitz.open(stream=file.read(), filetype="pdf")
                    for page_num in range(len(pdf_doc)):
                        pix = pdf_doc.load_page(page_num).get_pixmap(dpi=300)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        full_result.append(parse_format(parse_image_to_text_baidu(img)))
                elif file_name.endswith(('.jpg', '.png', '.jpeg')):
                    img = Image.open(file.stream)
                    full_result.append(parse_format(parse_image_to_text_baidu(img)))
            except Exception as e:
                full_result.append(f"【文件 {file.filename} 识别出错，可能余额不足或Key错误】")
        return "\n".join(full_result)
    return render_template_string(HTML_TEMPLATE, result="")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
