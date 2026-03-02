# -*- coding: utf-8 -*-
import os
import time
import uuid
import json
import requests
import zipfile
import io
from dotenv import load_dotenv

# ==========================================
# 0. 环境加载
# ==========================================
load_dotenv()

class PDFCloudLoader:
    """
    MinerU API 客户端 (V3.2 ZIP 适配版)
    增加了对 VLM 模式返回的 ZIP 包的自动解压与读取功能
    """
    
    def __init__(self):
        self.token = os.getenv("MINERU_API_TOKEN")
        if not self.token:
            raise ValueError("❌ [API] 环境变量 MINERU_API_TOKEN 缺失，请检查 .env 文件")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        self.base_url = "https://mineru.net/api/v4"

    def process(self, file_path: str) -> list:
        file_name = os.path.basename(file_path)
        print(f"\n☁️  [API] 开始云端采矿: {file_name}")
        
        try:
            # --- 1. 申请上传链接 ---
            data_id = str(uuid.uuid4())
            init_url = f"{self.base_url}/file-urls/batch"
            payload = {
                "files": [{"name": file_name, "data_id": data_id}],
                "model_version": "vlm" 
            }
            
            resp = requests.post(init_url, headers=self.headers, json=payload)
            res_json = resp.json()
            
            if resp.status_code != 200 or res_json.get("code") != 0:
                print(f"❌ [API] 申请失败: {res_json.get('msg')}")
                return []
            
            batch_id = res_json["data"]["batch_id"]
            upload_url = res_json["data"]["file_urls"][0]
            
            # --- 2. 上传文件 ---
            print(f"   -> 推送文件流 (Batch ID: {batch_id})")
            with open(file_path, 'rb') as f:
                requests.put(upload_url, data=f)
            
            # --- 3. 激活任务 ---
            extract_url = f"{self.base_url}/extract/batch"
            requests.post(extract_url, headers=self.headers, json={"batch_id": batch_id})
            print(f"   -> 任务已激活，启动深度轮询...")

            # --- 4. 轮询状态 ---
            query_url = f"{self.base_url}/extract-results/batch/{batch_id}"
            download_url = None
            is_zip = False
            
            # 轮询 100 次 (约 15 分钟)
            for i in range(100):
                time.sleep(10)
                try:
                    res = requests.get(query_url, headers=self.headers)
                    status_json = res.json()
                    extract_list = status_json.get("data", {}).get("extract_result", [])
                    
                    if not extract_list:
                        print(".", end="", flush=True)
                        continue

                    file_status = extract_list[0]
                    state = str(file_status.get("state", ""))
                    print(f"[{state}]", end="", flush=True)

                    # [核心修复]：优先找 markdown，找不到就找 full_zip_url
                    if file_status.get("markdown"):
                        download_url = file_status.get("markdown")
                        is_zip = False
                    elif file_status.get("full_zip_url"):
                        download_url = file_status.get("full_zip_url")
                        is_zip = True
                    
                    if state in ["success", "done", "7"] and download_url:
                        print("\n✅ [API] 云端处理完成！")
                        break
                    elif state in ["failed", "error", "-1"]:
                        print(f"\n❌ [API] 处理报错: {file_status.get('err_msg')}")
                        return []
                except:
                    pass
                
            if not download_url:
                print(f"\n❌ [TIMEOUT] 未能获取下载链接。")
                return []

            # --- 5. 下载与解包 (The Unpacking) ---
            print(f"   -> 正在下载产物 ({'ZIP包' if is_zip else '文本'})...")
            content_resp = requests.get(download_url)
            md_content = ""

            if is_zip:
                # 内存解压 ZIP
                try:
                    with zipfile.ZipFile(io.BytesIO(content_resp.content)) as z:
                        # 寻找 .md 文件
                        md_files = [f for f in z.namelist() if f.endswith('.md')]
                        if md_files:
                            # 读取第一个 md 文件
                            # MinerU 的 zip 通常结构是: folder/auto.md
                            target_md = md_files[0] 
                            with z.open(target_md) as f:
                                md_content = f.read().decode('utf-8')
                            print(f"   -> 已从 ZIP 中提取: {target_md}")
                        else:
                            print("❌ ZIP 包中未找到 Markdown 文件")
                except Exception as e:
                    print(f"❌ ZIP 解压失败: {e}")
                    return []
            else:
                # 直接是文本
                md_content = content_resp.text

            if not md_content.strip():
                print("⚠️ [API] 内容为空。")
                return []

            print(f"✅ [SUCCESS] 提取字符数: {len(md_content)}")
            
            return [{
                "chunk_id": str(uuid.uuid4()),
                "content": md_content,
                "metadata": {
                    "source": file_name,
                    "method": "MinerU_Cloud_VLM",
                    "batch_id": batch_id
                }
            }]

        except Exception as e:
            print(f"\n❌ [API] 异常: {e}")
            import traceback
            traceback.print_exc()
            return []

if __name__ == "__main__":
    loader = PDFCloudLoader()
    # 确保测试文件存在
    test_pdf = r"D:\KG_Test\raw_data\auto_mineru\test.pdf"
    if os.path.exists(test_pdf):
        loader.process(test_pdf)