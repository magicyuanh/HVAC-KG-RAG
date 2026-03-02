import json
import os
import random

# ================= 配置区域 =================
OUTPUT_FILENAME = "table_full_coverage.jsonl"
REPEAT_TIMES = 20  # 核心策略：每个知识点重复20遍，强行刻录进神经元

# ================= 核心原料：GB 50073-2013 表 3.0.1 绝对真值字典 =================
# 这是一个“无幻觉”的数据库，包含了表格里每一个有效的单元格
# N: {粒径: 限值}
TRUTH_TABLE = {
    "1": {
        "0.1μm": "10", 
        "0.2μm": "2"
    },
    "2": {
        "0.1μm": "100", 
        "0.2μm": "24", 
        "0.3μm": "10", 
        "0.5μm": "4"
    },
    "3": {
        "0.1μm": "1000", 
        "0.2μm": "237", 
        "0.3μm": "102", 
        "0.5μm": "35", 
        "1μm": "8"
    },
    "4": {
        "0.1μm": "10000", 
        "0.2μm": "2370", 
        "0.3μm": "1020", # 昨天的考点
        "0.5μm": "352",  # 昨天的混淆点
        "1μm": "83"
    },
    "5": {
        "0.1μm": "100000", 
        "0.2μm": "23700", 
        "0.3μm": "10200", 
        "0.5μm": "3520", # 昨天的痛点
        "1μm": "832", 
        "5μm": "29"
    },
    "6": {
        "0.1μm": "1000000", 
        "0.2μm": "237000", 
        "0.3μm": "102000", 
        "0.5μm": "35200", 
        "1μm": "8320", 
        "5μm": "293"
    },
    "7": {
        "0.5μm": "352000", 
        "1μm": "83200", 
        "5μm": "2930"
    },
    "8": {
        "0.5μm": "3520000", 
        "1μm": "832000", 
        "5μm": "29300"
    },
    "9": {
        "0.5μm": "35200000", 
        "1μm": "8320000", 
        "5μm": "293000"
    }
}

# 多样化提问模板 (让模型学会听懂各种问法)
QUESTION_TEMPLATES = [
    "根据 GB 50073-2013，{n}级洁净度对于 {size} 粒子的最大允许浓度限值是多少？",
    "洁净厂房设计规范中，空气洁净度等级 N={n} 时，{size} 粒子的浓度限值是多少？",
    "请查询规范表3.0.1：{n}级洁净度，{size} 粒子的上限。",
    "ISO {n}级（对应国标{n}级）在 {size} 粒径下的管控标准是多少？",
    "如果要达到{n}级洁净度，{size} 悬浮粒子的浓度不能超过多少？"
]

ANSWER_TEMPLATES = [
    "{limit} pc/m³",
    "限值为 {limit} pc/m³。",
    "根据表3.0.1，最大允许浓度为 {limit} pc/m³。",
    "{limit} 个/立方米"
]

def generate_data():
    print(f"🚀 正在启动“数值饱和攻击”生成程序...")
    print(f"🎯 目标：覆盖 1-9 级所有数据，每个数据点重复 {REPEAT_TIMES} 次")
    
    total_count = 0
    
    with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
        # 1. 遍历真值表
        for n, specs in TRUTH_TABLE.items():
            for size, limit in specs.items():
                
                # 针对每一个数据点，生成 REPEAT_TIMES 次数据
                for _ in range(REPEAT_TIMES):
                    # 随机组合问题和答案，增加泛化性
                    q_tmpl = random.choice(QUESTION_TEMPLATES)
                    a_tmpl = random.choice(ANSWER_TEMPLATES)
                    
                    instruction = q_tmpl.format(n=n, size=size)
                    output = a_tmpl.format(limit=limit)
                    
                    # 写入一行
                    data = {
                        "instruction": instruction,
                        "input": "",
                        "output": output
                    }
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    total_count += 1
            
            # 2. 增加“横向整行”记忆 (让模型记住一整行的关系)
            # 例如：5级包含哪些粒径？
            all_specs = ", ".join([f"{s}: {l}" for s, l in specs.items()])
            
            for _ in range(REPEAT_TIMES): # 同样重复20遍
                f.write(json.dumps({
                    "instruction": f"请列出 GB 50073-2013 中 {n} 级洁净度的所有粒径浓度限值。",
                    "input": "",
                    "output": f"{n}级洁净度的限值如下：{all_specs} (单位：pc/m³)"
                }, ensure_ascii=False) + "\n")
                total_count += 1

    print("\n" + "="*40)
    print(f"✅ 生成完成！文件：{OUTPUT_FILENAME}")
    print(f"📊 总数据量：{total_count} 条")
    print(f"🔥 这批数据包含了对“3520”和“352”的死记硬背训练，绝对稳！")
    print("="*40)

if __name__ == "__main__":
    generate_data()