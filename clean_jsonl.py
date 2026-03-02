import json
import os

# 配置路径
INPUT_FILE = r"D:\KG_Test\fine_tuning_data\sft_train_data.jsonl"
OUTPUT_FILE = r"D:\KG_Test\fine_tuning_data\final_clean_sft.jsonl"

def clean_data():
    print(f"🧹 开始清洗数据...")
    valid_count = 0
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f_in, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            try:
                data = json.loads(line)
                
                # 1. 核心字段提取 (丢弃 ner, relations 等杂质)
                new_data = {
                    "instruction": data.get("instruction", "").strip(),
                    "input": data.get("input", "").strip(),
                    "output": data.get("output", "").strip()
                }
                
                # 2. 质量熔断 (如果 instruction 或 output 为空，直接丢弃)
                if not new_data["instruction"] or not new_data["output"]:
                    continue
                
                # 3. 写入纯净版
                f_out.write(json.dumps(new_data, ensure_ascii=False) + "\n")
                valid_count += 1
                
            except Exception as e:
                print(f"⚠️ 跳过坏行: {e}")
                continue

    print(f"✅ 清洗完成！有效数据量: {valid_count} 条")
    print(f"💾 纯净文件已保存至: {OUTPUT_FILE}")

if __name__ == "__main__":
    clean_data()