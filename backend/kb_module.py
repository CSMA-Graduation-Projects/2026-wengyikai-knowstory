# kb_module.py
"""
知识增强模块：从数据库读取通用知识库，并根据用户输入需求进行命中匹配。
相比最初版本，本版本增加了简单归一化和组合词匹配，能够命中：
1. 注册登录类
2. 电商订单支付类
3. 用户管理类
"""
import json
import re
from typing import Dict, List, Any

from database import SessionLocal
from knowledge_models import KnowledgeModule


STOP_WORDS = ["类", "模块", "功能", "系统", "业务", "需求", "相关", "场景"]


def normalize_text(text: str) -> str:
    """对输入文本做简单清洗，减少“xx类”“xx模块”对匹配的影响。"""
    text = str(text or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    for word in STOP_WORDS:
        text = text.replace(word, "")
    return text


def loads_list(value: str) -> List[str]:
    try:
        data = json.loads(value or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def row_to_rules(row: KnowledgeModule) -> Dict[str, Any]:
    return {
        "aliases": loads_list(row.aliases),
        "必选要素": loads_list(row.required_elements),
        "前置条件": loads_list(row.preconditions),
        "异常场景": loads_list(row.exception_scenarios),
        "典型任务": loads_list(row.typical_tasks),
        "安全约束": row.security_constraints or "无特殊安全约束"
    }


def load_knowledge_base() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeModule).all()
        return {row.module_name: row_to_rules(row) for row in rows}
    finally:
        db.close()


def keyword_hit(requirement: str, keyword: str) -> bool:
    """同时使用原文本和归一化文本做包含匹配。"""
    if not keyword:
        return False

    raw_requirement = str(requirement or "")
    raw_keyword = str(keyword or "")

    if raw_keyword in raw_requirement:
        return True

    normalized_requirement = normalize_text(raw_requirement)
    normalized_keyword = normalize_text(raw_keyword)

    return bool(normalized_keyword and normalized_keyword in normalized_requirement)


def extract_matches(requirement: str, knowledge_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根据模块名和别名匹配知识库。
    例如：
    - “注册登录类”会命中“注册”“登录”；
    - “电商订单支付类”会命中“订单管理”“支付”；
    - “用户管理类”会命中“用户管理”。
    """
    matched_modules = []
    matched_names = set()

    for module_name, rules in knowledge_data.items():
        aliases = rules.get("aliases", [])
        keywords = [module_name] + aliases

        for keyword in keywords:
            if keyword_hit(requirement, keyword):
                if module_name not in matched_names:
                    matched_modules.append({"module": module_name, "rules": rules})
                    matched_names.add(module_name)
                break

    return matched_modules


def format_context(module_name: str, rules: Dict[str, Any]) -> str:
    required_elements = "、".join(rules.get("必选要素", [])) or "无"
    preconditions = "、".join(rules.get("前置条件", [])) or "无"
    exceptions = "、".join(rules.get("异常场景", [])) or "无"
    templates = "、".join(rules.get("典型任务", [])) or "无"
    security_constraints = rules.get("安全约束", "无特殊安全约束")

    return (
        f"【模块】{module_name}\n"
        f"【必选要素】{required_elements}\n"
        f"【前置条件】{preconditions}\n"
        f"【异常场景】{exceptions}\n"
        f"【典型任务】{templates}\n"
        f"【安全约束】{security_constraints}"
    )


def get_enhanced_payload(requirement: str) -> Dict[str, Any]:
    knowledge_data = load_knowledge_base()

    if not knowledge_data:
        return {
            "matched_modules": [],
            "context": "数据库知识库为空，请先运行 python seed_common_knowledge.py 初始化通用知识库。"
        }

    matched_modules = extract_matches(requirement, knowledge_data)

    if not matched_modules:
        return {
            "matched_modules": [],
            "context": "当前需求未命中专用知识库，请仅基于通用软件工程知识进行需求解析和任务拆解。"
        }

    context_blocks = [format_context(item["module"], item["rules"]) for item in matched_modules]

    return {
        "matched_modules": [item["module"] for item in matched_modules],
        "context": "\n\n".join(context_blocks)
    }


def get_enhanced_context(requirement: str) -> str:
    return get_enhanced_payload(requirement)["context"]
