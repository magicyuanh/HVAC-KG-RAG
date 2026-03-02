# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Dict, List, Optional
# 根目录引用
from config import AgentType

# 包内模块相对引用
from .monitoring import MonitoringManager

class PromptManager:
    """
    Prompt 管理器 (V3.2 宪法增强版)
    
    职责：
    1. [模板加载]：读取 Agent 的 TXT 指令模板。
    2. [宪法加载]：读取 Global Policy，作为最高准则。
    3. [动态注入]：将 Policy 和 Previous Context 缝合进 Prompt。
    4. [防爆转义]：保护 JSON 结构不被 format 函数误伤。
    """

    def __init__(self, prompt_dir: str, policy_path: str, monitor: MonitoringManager):
        """
        初始化管理器
        :param prompt_dir: 存放 .txt 模板的目录路径
        :param policy_path: 宪法文件 (.md) 的绝对路径
        :param monitor: 监控器实例
        """
        self.prompts: Dict[AgentType, str] = {}
        self.policy_content: str = ""
        self.monitor = monitor
        self.prompt_dir = Path(prompt_dir)
        self.policy_path = Path(policy_path)
        
        # 建立枚举类型与物理文件名的映射契约
        self.file_map = {
            AgentType.RADICAL: "1 激进派 ok.txt",
            AgentType.CONSERVATIVE: "2 保守派 ok.txt",
            AgentType.ADVERSARIAL: "3 对抗派 ok.txt",
            AgentType.JUDGE: "4 大法官 ok.txt"
        }
        
        # 初始化加载序列
        self._load_policy() # 先加载宪法
        self._load_templates() # 再加载模板

    def _load_policy(self):
        """加载全局本体论宪法 (Policy)"""
        if not self.policy_path.exists():
            self.monitor.log_step("PromptLoader", "Critical", f"宪法文件丢失: {self.policy_path}")
            # 这里不抛异常，允许空宪法运行（但会有警告），方便调试
            self.policy_content = "暂无全局策略限制。"
            return

        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                self.policy_content = f.read().strip()
            self.monitor.log_step("PromptLoader", "Success", f"宪法加载完毕 ({len(self.policy_content)} chars)")
        except Exception as e:
            self.monitor.log_step("PromptLoader", "Error", f"宪法读取失败: {e}")
            self.policy_content = "读取宪法文件时发生错误。"

    def _load_templates(self):
        """扫描并装载所有 Agent 的 Prompt 模板"""
        if not self.prompt_dir.exists():
            self.monitor.log_step("PromptLoader", "Error", f"未找到模板目录: {self.prompt_dir}")
            return

        for agent_type, filename in self.file_map.items():
            file_path = self.prompt_dir / filename
            try:
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        # 清洗标记
                        if "[file content begin]" in content:
                            content = content.split("[file content begin]")[-1]
                        if "[file content end]" in content:
                            content = content.split("[file content end]")[0]
                        
                        self.prompts[agent_type] = content.strip()
                else:
                    self.monitor.log_step("PromptLoader", "Warning", f"模板文件缺失: {filename}")
            except Exception as e:
                self.monitor.log_step("PromptLoader", "Error", f"读取模板 {filename} 失败: {e}")

    def get_prompt(self, agent_type: AgentType, **kwargs) -> str:
        """
        核心渲染逻辑 (V3.2 升级版)
        
        功能：
        1. 智能转义：保护 JSON 大括号。
        2. 自动注入：将 self.policy_content 注入 {global_policy}。
        3. 上下文填充：将 kwargs 中的 previous_context 注入。
        """
        raw_prompt = self.prompts.get(agent_type, "")
        if not raw_prompt:
            raise ValueError(f"警告：{agent_type.value} 的模板为空或未加载！")

        # --- 步骤 1: 建立“防爆装甲” ---
        # 全量转义：{{ }}
        escaped_prompt = raw_prompt.replace("{", "{{").replace("}", "}}")
        
        # --- 步骤 2: 恢复动态变量 (白名单扩充) ---
        # V3.2 新增了 global_policy 和 previous_context
        valid_placeholders = [
            "text",              # 原始文本 (Chunk Content)
            "radical_json",      # 激进派输出
            "conservative_json", # 保守派输出
            "critique",          # 质询报告
            "global_policy",     # [New] 全局宪法
            "previous_context"   # [New] 前文共识/记忆
        ]
        
        for p in valid_placeholders:
            # 恢复为单花括号 {key} 以便 format 识别
            escaped_prompt = escaped_prompt.replace(f"{{{{{p}}}}}", f"{{{p}}}")
            
        # --- 步骤 3: 自动参数注入 ---
        # 即使调用者没传 global_policy，这里也会自动填入
        if "global_policy" not in kwargs:
            kwargs["global_policy"] = self.policy_content
            
        # 如果没传 previous_context，默认为空提示
        if "previous_context" not in kwargs:
            kwargs["previous_context"] = "（无前文信息，这是文档的起始部分）"

        # --- 步骤 4: 最终渲染 ---
        try:
            return escaped_prompt.format(**kwargs)
        except KeyError as e:
            error_msg = f"Prompt 渲染失败：模板中包含未知的变量占位符 {e}"
            self.monitor.log_step("Prompt", "FormatError", error_msg)
            # 打印部分预览以便调试
            print(f"DEBUG: 模板预览: {raw_prompt[:100]}...")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Prompt 渲染发生未知异常: {e}"
            self.monitor.log_step("Prompt", "FormatError", error_msg)
            raise ValueError(error_msg)