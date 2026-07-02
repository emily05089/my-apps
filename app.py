import os
import re
import io
import fitz
from PIL import Image
from flask import Flask, request, render_template_string, jsonify
from aip import AipOcr

app = Flask(__name__)

# ==================== ⚠️ 填入你的百度 API 凭证 ====================
APP_ID = '123874873'           # 你的APP_ID
API_KEY = 'je80X5GVDpDMs1tC6ykZAyN3' # 你的API_KEY
SECRET_KEY = 'FMLU6MzUs21ujF7Y1wFIWCFv0nkeID7w' # 你的SECRET_KEY
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

# ==================== 网页前端（带进度条反馈） ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>双识别工具</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 15px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; }
        h1 { font-size: 22px; text-align: center; color: #333; }
        .row { display: flex; gap: 10px; margin: 15px 0; flex-wrap: wrap; }
        .btn { border: none; padding: 12px; border-radius: 8px; font-size: 14px; font-weight: bold; color: white; cursor: pointer; flex: 1; }
        .btn-add { background: #007bff; }
        .btn-start { background: #e60012; }
        .btn-clean { background: #6c757d; }
        .btn:active { opacity: 0.8; }
        .file-input { display: none; }
        
        .file-list { display: flex; flex-direction: column; gap: 10px; margin: 10px 0; border: 1px solid #eee; padding: 10px; border-radius: 8px; }
        .file-item { display: flex; justify-content: space-between; padding: 8px; background: #fafafa; border: 1px solid #ddd; border-radius: 6px; }
        .btn-del { background: #dc3545; padding: 4px 8px; font-size: 12px; flex: 0; }
        
        /* 进度条样式 */
        #progress-section { display: none; margin: 15px 0; }
        #progress-text { font-size: 14px; margin-bottom: 5px; }
        #progress-bar { width: 100%; height: 8px; background: #eee; border-radius: 4px; overflow: hidden; }
        #progress-fill { height: 100%; width: 0%; background: #e60012; border-radius: 4px; transition: width 0.2s; }

        textarea { width: 100%; height: 40vh; padding: 10px; border: 1px solid #ccc; border-radius: 8px; box-sizing: border-box; margin-top: 15px; font-size: 14px; }
        .copy-btn { background: #28a745; margin-top: 10px; flex: 1; }
        #error-message { display: none; color: red; margin-top: 10px; font-weight: bold; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📄 双识别工具</h1>
        <div class="row">
            <button class="btn btn-add" onclick="document.getElementById('fileInput').click()">➕ 添加文件</button>
            <button class="btn btn-clean" onclick="clearList()">🗑️ 清空</button>
            <button class="btn btn-start" onclick="startUpload()">🚀 识别全部</button>
        </div>
        <input type="file" id="fileInput" class="file-input" accept=".pdf,.jpg,.png,.jpeg" multiple onchange="handleFiles(this.files)">
        
        <div id="fileListContainer" class="file-list"><div style="color:#999; text-align:center;">等待添加...</div></div>
        
        <!-- 进度条展示区 -->
        <div id="progress-section">
            <div id="progress-text">准备中...</div>
            <div id="progress-bar"><div id="progress-fill"></div></div>
        </div>

        <div id="error-message"></div>
        
        <div>
            <textarea id="result" placeholder="识别结果将显示在这里">{{ result }}</textarea>
            <button class="btn copy-btn" onclick="copyText()">📋 复制结果</button>
        </div>
    </div>

    <script>
        let selectedFiles = [];
        function handleFiles(files) {
            for(let i=0; i<files.length; i++) selectedFiles.push(files[i]);
            renderList(); document.getElementById('fileInput').value = '';
        }
        function renderList() {
            const container = document.getElementById('fileListContainer');
            container.innerHTML = '';
            if(selectedFiles.length === 0){ container.innerHTML = '<div style="color:#999;text-align:center;">等待添加...</div>'; return; }
            for(let i=0; i<selectedFiles.length; i++){
                const f = selectedFiles[i];
                const item = document.createElement('div'); item.className = 'file-item';
                item.innerHTML = `<span>${f.name}</span><button class="btn btn-del" onclick="removeFile(${i})">删除</button>`;
                container.appendChild(item);
            }
        }
        function removeFile(i) { selectedFiles.splice(i,1); renderList(); }
        function clearList() { selectedFiles = []; renderList(); document.getElementById('result').value = ''; }

        async function startUpload() {
            if(selectedFiles.length === 0){ alert("请先添加文件！"); return; }
            
            // 清空旧结果，显示进度条
            document.getElementById('result').value = '';
            document.getElementById('error-message').style.display = 'none';
            const progSection = document.getElementById('progress-section');
            const progFill = document.getElementById('progress-fill');
            const progText = document.getElementById('progress-text');
            progSection.style.display = 'block';
            progFill.style.width = '0%';
            
            // 1. 告诉后台开始批量识别
            let formData = new FormData();
            for(let f of selectedFiles) formData.append('files', f);
            
            try {
                // 2. 监听后台进度的流式推送
                const response = await fetch('/stream_process', { method: 'POST', body: formData });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                // 3. 循环读取后台推送的进度
                while(true) {
                    const { done, value } = await reader.read();
                    if(done) break;
                    const msg = decoder.decode(value);
                    // 后台如果发来 "进度:当前/总数"，就更新进度条
                    if(msg.startsWith('进度:')) {
                        const parts = msg.replace('进度:', '').split('/');
                        const cur = parseInt(parts[0]);
                        const total = parseInt(parts[1]);
                        const pct = Math.round((cur / total) * 100);
                        progFill.style.width = pct + '%';
                        progText.innerText = `识别中 ${cur}/${total}`;
                    } else if(msg.startsWith('结果:')) {
                        // 最后收到结果，显示在文本框
                        document.getElementById('result').value = msg.replace('结果:', '');
                        progText.innerText = '识别完成！';
                        setTimeout(() => { progSection.style.display = 'none'; }, 2000);
                    }
                }
            } catch (error) {
                document.getElementById('error-message').innerText = "识别出错，请重试。";
                document.getElementById('error-message').style.display = 'block';
                progSection.style.display = 'none';
            }
        }

        function copyText() {
            var t = document.getElementById("result");
            t.select(); t.setSelectionRange(0, 99999);
            document.execCommand("copy"); alert("已复制！");
        }
    </script>
</body>
</html>
'''

# ==================== 核心API路由（支持流式推送进度） ====================
@app.route('/stream_process', methods=['POST'])
def stream_process():
    uploaded_files = request.files.getlist('files')
    total = len(uploaded_files)
    full_result = []
    
    # 定义一个生成器函数，逐步向浏览器推送数据
    def generate():
        yield f"进度:0/{total}\n"
        for idx, file in enumerate(uploaded_files):
            file_name = file.filename.lower()
            try:
                text_res = ""
                if file_name.endswith('.pdf'):
                    pdf_doc = fitz.open(stream=file.read(), filetype="pdf")
                    for page_num in range(len(pdf_doc)):
                        pix = pdf_doc.load_page(page_num).get_pixmap(dpi=300)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        text_res += parse_format(parse_image_to_text_baidu(img)) + "\n"
                elif file_name.endswith(('.jpg', '.png', '.jpeg')):
                    img = Image.open(file.stream)
                    text_res = parse_format(parse_image_to_text_baidu(img))
                
                full_result.append(text_res)
                # 每处理完一张，就推送一次进度
                yield f"进度:{idx+1}/{total}\n"
            except Exception as e:
                full_result.append(f"【{file.filename} 识别失败】")
        
        # 全部处理完，推送最终结果
        yield f"结果:{''.join(full_result)}"
        
    return app.response_class(generate(), mimetype='text/plain')

@app.route('/', methods=['GET', 'POST'])
def index():
    # 普通页面加载，保持不变
    return render_template_string(HTML_TEMPLATE, result="")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
