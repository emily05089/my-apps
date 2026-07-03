import os
import re
import io
import fitz
from PIL import Image
from flask import Flask, request, render_template_string
from aip import AipOcr

app = Flask(__name__)

# ==================== ⚠️ 填入你的百度 API 凭证 ====================
APP_ID = '你的AppID'
API_KEY = '你的API Key'
SECRET_KEY = '你的Secret Key'
# ===================================================================

client = AipOcr(APP_ID, API_KEY, SECRET_KEY)

def parse_image_to_text_baidu(img):
    try:
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        image_bytes = img_byte_arr.getvalue()
        options = {"language_type": "CHN_ENG", "detect_direction": "true"}
        result = client.basicAccurate(image_bytes, options)
        text = ""
        if 'words_result' in result:
            for item in result['words_result']:
                text += item['words'] + "\n"
        return text
    except Exception as e:
        print("百度识别异常:", e)
        return ""

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

# ==================== 极度精简、稳定的网页前端 ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>双识别工具</title>
    <style>
        body { font-family: -apple-system, sans-serif; padding: 15px; }
        .btn { border: none; padding: 10px 20px; border-radius: 5px; color: white; cursor: pointer; }
        .btn-start { background: #e60012; }
        .btn-clean { background: #6c757d; }
        textarea { width: 100%; height: 60vh; margin-top: 10px; }
        #loading { display: none; color: red; }
    </style>
</head>
<body>
    <h1>双识别工具</h1>
    <div>
        <button class="btn" style="background:#007bff;" onclick="document.getElementById('fileInput').click()">添加图片/PDF</button>
        <button class="btn btn-clean" onclick="clearList()">清空</button>
        <button class="btn btn-start" onclick="uploadFiles()">识别全部</button>
    </div>
    <input type="file" id="fileInput" style="display:none" accept=".pdf,.jpg,.png,.jpeg" multiple onchange="handleFiles(this.files)">
    
    <div id="fileList" style="margin:10px 0;"></div>
    <div id="loading">⏳ 正在识别，请稍候...</div>
    
    <div>
        <textarea id="result" placeholder="识别结果将在此显示">{{ result }}</textarea>
        <button class="btn" style="background:#28a745;margin-top:10px;" onclick="copyText()">复制全部结果</button>
    </div>

    <script>
        let files = [];
        function handleFiles(f) {
            for(let i=0; i<f.length; i++) files.push(f[i]);
            renderList();
            document.getElementById('fileInput').value = '';
        }
        function renderList() {
            let html = '<ul>';
            for(let i=0; i<files.length; i++) {
                html += `<li>${files[i].name} <button onclick="remove(${i})">删除</button></li>`;
            }
            document.getElementById('fileList').innerHTML = html + '</ul>';
        }
        function remove(i) { files.splice(i,1); renderList(); }
        function clearList() { files = []; renderList(); }
        async function uploadFiles() {
            if(files.length===0){alert("请先添加文件");return;}
            document.getElementById('loading').style.display = 'block';
            let formData = new FormData();
            for(let f of files) formData.append('files', f);
            let res = await fetch('/', {method:'POST', body:formData});
            let text = await res.text();
            document.getElementById('result').value = text;
            document.getElementById('loading').style.display = 'none';
        }
        function copyText() {
            let t = document.getElementById('result');
            t.select(); document.execCommand('copy'); alert("已复制！");
        }
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
                full_result.append(f"【{file.filename} 识别失败】")
        return "\n".join(full_result)
    return render_template_string(HTML_TEMPLATE, result="")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
