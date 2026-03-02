import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# ==============================================================================
# 1. 路径与配置
# ==============================================================================

BASE_DIR = r"D:\KG_Test"

# 数据存放目录
DATA_DIR = os.path.join(BASE_DIR, "fine_tuning_data")
INPUT_DIR = os.path.join(BASE_DIR, "jsonl")

# 配置文件 .env 路径
ENV_PATH = os.path.join(BASE_DIR, ".env")

# 本体策略文件路径
ONTOLOGY_PATH = os.path.join(BASE_DIR, "Global_HVACR_Ontology_Policy V1.5.0.md")

# 输入文件名
INPUT_FILENAME = "structured_chunks.jsonl"

# 输出文件名 (注意：每次运行前最好清理或改名，避免追加太旧数据)
OUTPUT_FILENAME = "sft_train_data.jsonl"

INPUT_FILE = os.path.join(INPUT_DIR, INPUT_FILENAME)
OUTPUT_FILE = os.path.join(DATA_DIR, OUTPUT_FILENAME)

# ==============================================================================
# 2. 环境初始化
# ==============================================================================

# 从 .env 加载环境变量
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"✅ 已加载配置文件: {ENV_PATH}")
else:
    print(f"❌ 未找到配置文件: {ENV_PATH}，请检查路径！")
    exit(1)

# 获取 API Key
API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not API_KEY:
    print("❌ 未读取到 API Key，请检查 .env 文件内容！")
    exit(1)

# 初始化 DeepSeek 客户端
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

# ==============================================================================
# 3. 读取本地本体策略文件
# ==============================================================================

def load_ontology():
    """读取本体 Markdown 文件内容作为 Prompt 的核心约束"""
    if not os.path.exists(ONTOLOGY_PATH):
        print(f"❌ 未找到本体文件: {ONTOLOGY_PATH}")
        return ""
    
    with open(ONTOLOGY_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"✅ 已加载本体策略文件，长度: {len(content)} 字符")
    return content

# 加载本体内容
ONTOLOGY_CONTENT = load_ontology()

# ==============================================================================
# 4. 核心处理逻辑 (修复版)
# ==============================================================================

def clean_json_string(s):
    """清洗 LLM 返回的字符串，提取 JSON 部分"""
    s = re.sub(r'```json\s*', '', s)
    s = re.sub(r'```\s*$', '', s)
    return s.strip()

def extract_qa_from_raw_text(raw_text):
    """正则挽救模式：从乱码中强行提取 JSON"""
    potential_items = re.findall(r'\{[^{}]*"instruction"[^{}]*"[^{}]*"output"[^{}]*\}', raw_text)
    valid_items = []
    for item_str in potential_items:
        try:
            valid_items.append(json.loads(item_str))
        except json.JSONDecodeError:
            continue
    return valid_items

def robust_parse_qa(content):
    """稳健解析器：先正常解析，失败后用正则挖"""
    try:
        cleaned = clean_json_string(content)
        return json.loads(cleaned)
    except Exception as e:
        print(f"⚠️ JSON 格式异常，启动正则挖掘模式...")
        return extract_qa_from_raw_text(content)

def generate_qa_with_reasoner(chunk_content):
    """调用 deepseek-reasoner 生成符合本体规范的 Q&A (强制扩容版)"""
    
    # 构造 System Prompt
    # 注意：这是一个“激进版” Prompt，旨在榨取数据
    system_prompt = f"""
    你是《洁净厂房设计规范》顶级数据挖掘专家。
    你的任务是根据给定的文本片段，遵循以下《Global_HVACR_Ontology_Policy V1.5.0》规范，提炼出高质量的微调数据集。
    
    【核心宪法：Global_HVACR_Ontology_Policy V1.5.0】
    {ONTOLOGY_CONTENT}
    
    【暴裂挖掘任务 - 强制执行】
    你的目标是**尽可能多**地生成高质量问答对。
    1. **强制数量**：必须生成 10-12 对问答对。
    2. **禁止空值**：严禁返回空列表 []。即使文本只有一行字，也必须编题。
    3. **五维裂变**：
       - 【定义类】：精准解释术语、概念。
       - 【数值类】：压榨每一个参数、限值、计算公式及单位。
       - 【合规类】：针对“必须”、“应”、“严禁”条文提问。
       - 【原理类】：解释规定背后的物理逻辑。
       - 【场景类】：模拟工程现场、验收场景或故障排查。
    
    【输出格式】
    1. **严格遵守上述策略中的数值格式、Unicode单位（如 m³, ℃, ≥）、和实体保护规则。**
    2. 输出格式必须为 JSON 列表：`[{{"instruction": "...", "input": "", "output": "..."}}, ...]`
    3. Instruction (问题) 要专业、具体，类似考试题或工程咨询。
    4. Output (回答) 要严谨，逻辑通顺，基于原文。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【待处理文本片段】：\n{chunk_content}"}
            ],
            stream=False
        )
        
        content = response.choices[0].message.content
        qa_list = robust_parse_qa(content)
        
        if not qa_list:
             print("⚠️ 警告：该块数据极度异常，模型未能产出任何 JSON。")
             
        return qa_list

    except Exception as e:
        print(f"❌ API 调用出错: {e}")
        return []

# ==============================================================================
# 5. 主程序入口
# ==============================================================================

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 输入文件不存在: {INPUT_FILE}")
        return

    print(f"🚀 开始处理 (激进扩容模式)...")
    print(f"📂 输入文件: {INPUT_FILE}")
    print(f"📂 输出文件: {OUTPUT_FILE}")

    # 计算总行数
    total_lines = sum(1 for _ in open(INPUT_FILE, 'r', encoding='utf-8'))
    
    processed_count = 0
    generated_pairs = 0

    # 打开输入和输出文件
    with open(INPUT_FILE, 'r', encoding='utf-8') as f_in, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
        
        # 使用 tqdm 显示进度条
        for line in tqdm(f_in, total=total_lines, desc="Processing Chunks"):
            line = line.strip()
            if not line:
                continue
            
            try:
                # 解析原始 JSONL 行
                data = json.loads(line)
                raw_content = data.get("content", "")
                
                # 简单过滤
                if len(raw_content) < 15:
                    continue
                
                # 调用 AI 生成
                qa_list = generate_qa_with_reasoner(raw_content)
                
                # 写入结果
                if qa_list and isinstance(qa_list, list):
                    for qa in qa_list:
                        # 确保字段完整
                        if "instruction" in qa and "output" in qa:
                            if "input" not in qa:
                                qa["input"] = ""
                            
                            # 写入一行 JSONL
                            f_out.write(json.dumps(qa, ensure_ascii=False) + "\n")
                            generated_pairs += 1
                
                processed_count += 1
                
            except json.JSONDecodeError:
                print("⚠️ 跳过无法解析的行")
                continue
            except Exception as e:
                print(f"⚠️ 处理出错: {e}")
                continue

    print("\n" + "="*50)
    print(f"✅ 处理完成！")
    print(f"📊 处理 Chunk 数: {processed_count}/{total_lines}")
    print(f"📝 生成 Q&A 对数: {generated_pairs}")
    print(f"💾 结果已保存至: {OUTPUT_FILE}")
    
    if processed_count < 10:
        print("⚠️ 提示：处理量极少，请检查输入文件路径是否正确。")
    elif processed_count < 50:
        print("⚠️ 提示：处理量较少，请检查环境。")

if __name__ == "__main__":
    main()
