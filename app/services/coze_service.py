"""
Coze Workflow 集成服务
"""
import httpx
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from app.config import settings

# 配置日志 - 设置为 DEBUG 级别以显示详细信息
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def analyze_customer_kyc(
    kyc_data: dict,
    related_contacts: Optional[List[dict]] = None
) -> dict:
    """
    调用 Coze Workflow API 进行智能分析
    
    Prompt 增强逻辑：
    1. 基于 kyc_data 生成移民方案建议
    2. 基于家庭结构 (children_count, children_education) 挖掘教育商机
    3. 基于关联人 (related_contacts) 推荐转介绍机会
    
    Args:
        kyc_data: KYC 表单数据
        related_contacts: 关联人信息
    
    Returns:
        {
            "report": "Markdown格式的分析报告",
            "opportunities": [
                {"type": "子女教育", "description": "...", "priority": "high"},
                {"type": "养老规划", "description": "...", "priority": "medium"}
            ]
        }
    """
    # 如果未配置 Coze API，返回模拟数据
    if not settings.COZE_API_KEY or not settings.COZE_WORKFLOW_ID:
        logger.info("未配置 Coze API，使用模拟数据")
        return _generate_mock_analysis(kyc_data, related_contacts)
    
    # 构建请求数据
    workflow_input = _build_workflow_input(kyc_data, related_contacts)
    
    # 构建请求信息
    request_url = f"{settings.COZE_API_BASE_URL}/workflow/run"
    request_headers = {
        "Authorization": f"Bearer {settings.COZE_API_KEY[:20]}...（已隐藏）",
        "Content-Type": "application/json"
    }
    request_body = {
        "workflow_id": settings.COZE_WORKFLOW_ID,
        "parameters": workflow_input
    }
    
    # 打印详细的请求信息
    print("\n" + "="*60)
    print("🚀 [COZE API] 发送请求")
    print("="*60)
    print(f"📍 请求地址: {request_url}")
    print(f"📋 Workflow ID: {settings.COZE_WORKFLOW_ID}")
    print(f"📤 请求头:")
    for key, value in request_headers.items():
        print(f"   {key}: {value}")
    print(f"📦 请求体 (parameters):")
    print(json.dumps(workflow_input, ensure_ascii=False, indent=2))
    print("-"*60)
    
    try:
        logger.info(f"调用 Coze API: workflow_id={settings.COZE_WORKFLOW_ID}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                request_url,
                headers={
                    "Authorization": f"Bearer {settings.COZE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            
            # 打印详细的响应信息
            print("\n" + "="*60)
            print("📥 [COZE API] 收到响应")
            print("="*60)
            print(f"📊 状态码: {response.status_code}")
            print(f"📋 响应头:")
            for key, value in response.headers.items():
                print(f"   {key}: {value}")
            
            # 获取原始响应文本
            raw_text = response.text
            print(f"📄 响应体 (原始):")
            print("-"*40)
            # 格式化输出 JSON
            try:
                formatted_response = json.dumps(json.loads(raw_text), ensure_ascii=False, indent=2)
                print(formatted_response)
            except:
                print(raw_text[:2000] if len(raw_text) > 2000 else raw_text)
            print("-"*40)
            
            logger.info(f"Coze API 响应状态: {response.status_code}")
            
            response.raise_for_status()
            
            # 尝试解析 JSON 响应
            try:
                result = response.json()
                print(f"✅ JSON 解析成功，数据类型: {type(result).__name__}")
            except json.JSONDecodeError as e:
                # 如果不是 JSON，尝试作为纯文本处理
                print(f"⚠️ JSON 解析失败: {str(e)}")
                logger.warning(f"Coze API 返回非 JSON 格式: {raw_text[:200]}")
                return {
                    "report": raw_text,
                    "opportunities": []
                }
            
            logger.info(f"Coze API 响应解析成功: {type(result)}")
            
            # 解析 Coze 返回结果
            parsed_result = _parse_coze_response(result)
            
            print("\n" + "="*60)
            print("📋 [COZE API] 解析结果")
            print("="*60)
            print(f"📝 报告长度: {len(parsed_result.get('report', ''))} 字符")
            print(f"💡 商机数量: {len(parsed_result.get('opportunities', []))} 个")
            if parsed_result.get('report'):
                print(f"📄 报告预览 (前500字):")
                print("-"*40)
                print(parsed_result['report'][:500])
                print("-"*40)
            print("="*60 + "\n")
            
            return parsed_result
            
    except httpx.TimeoutException as e:
        print(f"\n❌ [COZE API] 请求超时: {str(e)}")
        logger.error(f"Coze API 请求超时: {str(e)}")
        # 超时时回退到模拟数据
        print("⚠️ 使用模拟数据代替")
        logger.info("API 超时，使用模拟数据")
        return _generate_mock_analysis(kyc_data, related_contacts)
    except httpx.HTTPStatusError as e:
        print(f"\n❌ [COZE API] HTTP 错误: {e.response.status_code}")
        print(f"📄 错误响应: {e.response.text}")
        logger.error(f"Coze API HTTP 错误: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Coze API 请求失败: {e.response.status_code}")
    except Exception as e:
        print(f"\n❌ [COZE API] 异常: {type(e).__name__}: {str(e)}")
        logger.error(f"Coze 服务异常: {type(e).__name__}: {str(e)}")
        raise Exception(f"Coze 服务异常: {str(e)}")


def _build_workflow_input(
    kyc_data: dict,
    related_contacts: Optional[List[dict]]
) -> dict:
    """构建 Coze Workflow 输入参数"""
    
    # 将 KYC 数据和关联人信息合并为一个完整的表单数据
    form_data = {
        **kyc_data,  # 包含所有原始 KYC 表单字段
        "related_contacts": related_contacts or []  # 添加关联人信息
    }
    
    # Workflow 只接受一个 kyc_form_data 参数
    return {
        "kyc_form_data": json.dumps(form_data, ensure_ascii=False)
    }


def _parse_coze_response(result: dict) -> dict:
    """解析 Coze API 返回结果"""
    print("\n" + "-"*40)
    print("🔍 [解析] 开始解析 Coze 响应")
    print("-"*40)
    logger.debug(f"解析 Coze 响应: {json.dumps(result, ensure_ascii=False)[:500]}")
    
    # 检查响应中的错误码
    code = result.get("code", 0)
    print(f"   📌 响应码 (code): {code}")
    if code != 0:
        error_msg = result.get("msg", result.get("message", "未知错误"))
        print(f"   ❌ API 返回错误: {error_msg}")
        logger.error(f"Coze API 返回错误: code={code}, msg={error_msg}")
        raise Exception(f"Coze API 错误: {error_msg}")
    
    # 尝试从多种可能的响应格式中提取数据
    data = result.get("data")
    print(f"   📌 data 字段存在: {data is not None}")
    print(f"   📌 data 类型: {type(data).__name__ if data is not None else 'None'}")
    
    # 如果 data 为空，尝试其他字段
    if data is None:
        print("   ⚠️ data 为空，尝试其他字段...")
        # 可能整个 result 就是数据
        if "report" in result:
            print("   ✅ 找到 report 字段")
            return {
                "report": result.get("report", ""),
                "opportunities": result.get("opportunities", [])
            }
        # 尝试 output 字段
        data = result.get("output", result.get("result", ""))
        print(f"   📌 尝试 output/result 字段: {type(data).__name__}")
    
    if isinstance(data, str):
        print(f"   📌 data 是字符串，长度: {len(data)}")
        print(f"   📌 data 内容预览: {data[:200]}...")
    elif isinstance(data, dict):
        print(f"   📌 data 是字典，键: {list(data.keys())}")
    elif isinstance(data, list):
        print(f"   📌 data 是列表，长度: {len(data)}")
    
    logger.debug(f"提取的 data 类型: {type(data)}, 值: {str(data)[:200]}")
    
    # 如果 data 是字符串，尝试解析为 JSON
    if isinstance(data, str):
        print("   🔄 尝试将字符串 data 解析为 JSON...")
        # 尝试解析 JSON
        try:
            parsed = json.loads(data)
            print(f"   ✅ JSON 解析成功，结果类型: {type(parsed).__name__}")
            if isinstance(parsed, dict):
                print(f"   📌 解析后的字典键: {list(parsed.keys())}")
                data = parsed
            else:
                # 解析成功但不是字典，将其作为报告内容
                print("   ⚠️ 解析结果不是字典，作为报告返回")
                return {
                    "report": str(parsed),
                    "opportunities": []
                }
        except json.JSONDecodeError as e:
            # 不是 JSON，直接作为报告内容
            print(f"   ⚠️ JSON 解析失败: {str(e)}")
            print("   📝 将字符串直接作为报告返回")
            logger.info("data 字段为纯文本，作为报告返回")
            return {
                "report": data,
                "opportunities": []
            }
    
    # 如果 data 是字典
    if isinstance(data, dict):
        print("   📌 处理字典类型的 data")

        # Coze workflow 常见格式：{content_type:1, data:"<markdown>", ...}
        if "data" in data:
            inner_data = data.get("data")
            if isinstance(inner_data, str):
                print("   ✅ 发现 data 字段为字符串，直接作为报告使用")
                print(f"      - 报告长度: {len(inner_data)} 字符")
                return {
                    "report": inner_data,
                    "opportunities": data.get("opportunities", [])
                }
            if isinstance(inner_data, dict):
                print("   ✅ 发现 data 字段为字典，尝试提取 report/opportunities")
                return {
                    "report": inner_data.get("report", inner_data.get("content", "")),
                    "opportunities": inner_data.get("opportunities", [])
                }

        # 检查是否有嵌套的 output 字段（某些 workflow 格式）
        if "output" in data and isinstance(data["output"], str):
            print("   🔄 发现嵌套的 output 字段，尝试解析...")
            try:
                output = json.loads(data["output"])
                if isinstance(output, dict):
                    print(f"   ✅ output 解析成功，键: {list(output.keys())}")
                    return {
                        "report": output.get("report", ""),
                        "opportunities": output.get("opportunities", [])
                    }
            except json.JSONDecodeError:
                print("   ⚠️ output 不是 JSON，作为报告返回")
                return {
                    "report": data["output"],
                    "opportunities": []
                }
        
        # 标准格式
        report = data.get("report", data.get("content", ""))
        opportunities = data.get("opportunities", [])
        print(f"   ✅ 使用标准格式提取:")
        print(f"      - report 来源: {'report' if 'report' in data else ('content' if 'content' in data else '无')}")
        print(f"      - report 长度: {len(report)} 字符")
        print(f"      - opportunities 数量: {len(opportunities)}")
        return {
            "report": report,
            "opportunities": opportunities
        }
    
    # 如果 data 是列表（可能是事件流格式的结果）
    if isinstance(data, list):
        print(f"   📌 处理列表类型的 data，长度: {len(data)}")
        # 尝试从列表中提取最后的 Message 事件内容
        for i, item in enumerate(reversed(data)):
            if isinstance(item, dict):
                print(f"   🔍 检查列表项 [{len(data)-1-i}]: {list(item.keys())}")
                content = item.get("content", item.get("data", {}).get("content"))
                if content:
                    print(f"   ✅ 找到 content: {str(content)[:100]}...")
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict):
                            return {
                                "report": parsed.get("report", content),
                                "opportunities": parsed.get("opportunities", [])
                            }
                    except (json.JSONDecodeError, TypeError):
                        return {
                            "report": str(content),
                            "opportunities": []
                        }
    
    # 兜底：将整个结果转为字符串作为报告
    print("   ⚠️ 无法解析 Coze 响应格式，使用原始数据作为报告")
    logger.warning(f"无法解析 Coze 响应格式，使用原始数据")
    print("-"*40)
    return {
        "report": str(data) if data else "",
        "opportunities": []
    }


async def analyze_customer_kyc_stream(
    kyc_data: dict,
    related_contacts: Optional[List[dict]] = None
) -> AsyncGenerator[str, None]:
    """
    调用 Coze Workflow API 进行智能分析 - 流式输出版本
    
    使用 SSE (Server-Sent Events) 格式返回流式数据
    
    Args:
        kyc_data: KYC 表单数据
        related_contacts: 关联人信息
    
    Yields:
        SSE 格式的流式数据块
    """
    # 如果未配置 Coze API，返回模拟数据（流式）
    if not settings.COZE_API_KEY or not settings.COZE_WORKFLOW_ID:
        logger.info("未配置 Coze API，使用模拟流式数据")
        mock_result = _generate_mock_analysis(kyc_data, related_contacts)
        # 模拟流式输出
        report = mock_result.get("report", "")
        for i in range(0, len(report), 20):
            chunk = report[i:i+20]
            yield f"data: {json.dumps({'type': 'content', 'content': chunk}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)
        # 发送完成事件
        yield f"data: {json.dumps({'type': 'done', 'opportunities': mock_result.get('opportunities', [])}, ensure_ascii=False)}\n\n"
        return
    
    # 构建请求数据
    workflow_input = _build_workflow_input(kyc_data, related_contacts)
    
    # 流式 API 端点
    request_url = f"{settings.COZE_API_BASE_URL}/workflow/stream_run"
    request_body = {
        "workflow_id": settings.COZE_WORKFLOW_ID,
        "parameters": workflow_input
    }
    
    print("\n" + "="*60)
    print("🚀 [COZE API] 发送流式请求")
    print("="*60)
    print(f"📍 请求地址: {request_url}")
    print(f"📋 Workflow ID: {settings.COZE_WORKFLOW_ID}")
    print("-"*60)
    
    accumulated_content = ""
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                request_url,
                headers={
                    "Authorization": f"Bearer {settings.COZE_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"
                },
                json=request_body
            ) as response:
                print(f"📊 流式响应状态码: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"❌ 流式请求失败: {error_text.decode()}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'API错误: {response.status_code}'}, ensure_ascii=False)}\n\n"
                    return
                
                # 处理 SSE 流
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # 按行处理 SSE 数据
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        # 处理 SSE 数据行
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue
                            
                            try:
                                data = json.loads(data_str)
                                event_type = data.get("event", data.get("type", ""))
                                
                                print(f"📦 收到事件: {event_type}")
                                
                                # 处理不同类型的事件
                                if event_type == "Message":
                                    # Coze workflow 消息事件
                                    message_data = data.get("data", data.get("message", {}))
                                    if isinstance(message_data, str):
                                        try:
                                            message_data = json.loads(message_data)
                                        except:
                                            pass
                                    
                                    content = ""
                                    if isinstance(message_data, dict):
                                        content = message_data.get("content", message_data.get("data", ""))
                                    elif isinstance(message_data, str):
                                        content = message_data
                                    
                                    if content:
                                        accumulated_content += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                                
                                elif event_type in ["Output", "output"]:
                                    # 输出节点数据
                                    output_data = data.get("data", data.get("output", ""))
                                    if isinstance(output_data, str):
                                        try:
                                            output_data = json.loads(output_data)
                                        except:
                                            pass
                                    
                                    content = ""
                                    if isinstance(output_data, dict):
                                        content = output_data.get("data", output_data.get("content", output_data.get("output", "")))
                                    elif isinstance(output_data, str):
                                        content = output_data
                                    
                                    if content:
                                        accumulated_content += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                                
                                elif event_type in ["Done", "done", "Completed", "completed"]:
                                    # 完成事件
                                    print("✅ 流式输出完成")
                                    yield f"data: {json.dumps({'type': 'done', 'opportunities': []}, ensure_ascii=False)}\n\n"
                                
                                elif event_type in ["Error", "error"]:
                                    # 错误事件
                                    error_msg = data.get("message", data.get("error", "未知错误"))
                                    print(f"❌ 错误事件: {error_msg}")
                                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
                                
                                else:
                                    # 其他事件，尝试提取内容
                                    content = data.get("content", data.get("data", ""))
                                    if isinstance(content, str) and content:
                                        accumulated_content += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                            
                            except json.JSONDecodeError as e:
                                print(f"⚠️ JSON 解析失败: {data_str[:100]}...")
                                # 直接作为文本内容输出
                                if data_str and data_str != "[DONE]":
                                    accumulated_content += data_str
                                    yield f"data: {json.dumps({'type': 'content', 'content': data_str}, ensure_ascii=False)}\n\n"
                        
                        elif line.startswith("event:"):
                            # 事件类型行，忽略
                            pass
                
                # 处理剩余的 buffer
                if buffer.strip():
                    if buffer.strip().startswith("data:"):
                        data_str = buffer.strip()[5:].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)
                                content = data.get("content", data.get("data", ""))
                                if content:
                                    accumulated_content += content
                                    yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                            except:
                                accumulated_content += data_str
                                yield f"data: {json.dumps({'type': 'content', 'content': data_str}, ensure_ascii=False)}\n\n"
                
                # 发送最终完成事件
                print(f"📝 总共接收内容长度: {len(accumulated_content)} 字符")
                yield f"data: {json.dumps({'type': 'done', 'full_content': accumulated_content, 'opportunities': []}, ensure_ascii=False)}\n\n"
                
    except httpx.TimeoutException as e:
        print(f"❌ 流式请求超时: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': '请求超时'}, ensure_ascii=False)}\n\n"
    except Exception as e:
        print(f"❌ 流式请求异常: {type(e).__name__}: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


def _normalize_asset_level(asset_level: str) -> str:
    """
    将旧版 A8/A9/A10/A11 资产级别映射到新版区间描述
    """
    if not asset_level:
        return "未知"
    
    # 旧版映射表
    old_to_new = {
        "A8 (百万级)": "100-500万",
        "A9 (千万级)": "2000万-1亿",
        "A10 (亿级)": "1亿以上",
        "A11 (十亿级)": "1亿以上",
    }
    
    # 如果是旧版格式，转换为新版
    if asset_level in old_to_new:
        return old_to_new[asset_level]
    
    # 已经是新版格式，直接返回
    return asset_level


def _generate_mock_analysis(
    kyc_data: dict,
    related_contacts: Optional[List[dict]]
) -> dict:
    """
    生成模拟分析结果（用于未配置 Coze API 时）
    """
    name = kyc_data.get("name", "客户")
    target_countries = kyc_data.get("target_countries", [])
    core_needs = kyc_data.get("core_needs", [])
    children_count = kyc_data.get("children_count", 0)
    children_education = kyc_data.get("children_education", [])
    asset_level = _normalize_asset_level(kyc_data.get("asset_level", ""))
    timeline = kyc_data.get("timeline", "")
    
    # 新增字段
    first_education = kyc_data.get("first_education", "")
    education = kyc_data.get("education", "")
    education_certifications = kyc_data.get("education_certifications", [])
    industry_category = kyc_data.get("industry_category", "")
    residency_requirement = kyc_data.get("residency_requirement", "")
    
    # 生成报告
    countries_text = "、".join(target_countries) if target_countries else "未指定"
    needs_text = "、".join(core_needs) if core_needs else "未指定"
    cert_text = "、".join(education_certifications) if education_certifications else "无"
    
    # 居住要求分析
    residency_analysis = ""
    if residency_requirement:
        if "≥300天" in residency_requirement:
            residency_analysis = "客户可满足严格的居住要求（如西班牙、葡萄牙黄金签证的居住要求）"
        elif "≥180天" in residency_requirement:
            residency_analysis = "客户可满足中等居住要求（如香港优才续签、新加坡PR维持）"
        elif "<180天" in residency_requirement:
            residency_analysis = "客户居住时间有限，建议优先考虑无居住要求或低居住要求的项目"
        else:
            residency_analysis = "居住意愿待确认，需进一步沟通"
    
    report = f"""# {name} 移民方案分析报告

## 一、客户画像

- **意向国家**: {countries_text}
- **核心诉求**: {needs_text}
- **资产规模**: {asset_level or "未知"}
- **所属行业**: {industry_category or "未指定"}
- **最高学历**: {education or "未知"}（第一学历：{first_education or "未知"}）
- **学历认证**: {cert_text}
- **办理周期**: {timeline or "未指定"}
- **家庭情况**: {children_count} 位子女
- **居住意愿**: {residency_requirement or "未指定"}

### 居住要求分析
{residency_analysis or "暂无"}

## 二、方案建议

### 推荐方案一：新加坡家族办公室
适合高净值人士，税务优化效果显著，子女可享受优质国际教育资源。

**优势**：
- 无外汇管制
- 税率低（个人所得税最高22%）
- 教育资源丰富

**周期**: 6-12个月

### 推荐方案二：香港优才计划
适合有一定学历或专业背景的申请人，审批周期相对较快。

**优势**：
- 无需投资
- 保留内地身份
- 子女可参加华侨生联考

**周期**: 4-8个月

## 三、注意事项

1. 建议尽早准备相关文件
2. 资产证明需提前3个月整理
3. 子女教育规划需同步进行

---
*本报告由 AI 智能分析生成，仅供参考。具体方案请咨询专业顾问。*
"""

    # 生成商机
    opportunities = []
    
    # 基于家庭结构分析商机
    if children_count and children_count > 0:
        if children_education:
            if "高中" in children_education or "初中" in children_education:
                opportunities.append({
                    "type": "子女教育",
                    "description": f"客户有子女正处于{'/'.join(children_education)}阶段，可推荐国际学校规划、留学预科等服务。",
                    "priority": "high"
                })
            if "本科" in children_education or "研究生" in children_education:
                opportunities.append({
                    "type": "留学深造",
                    "description": "子女已进入高等教育阶段，可推荐海外研究生申请、职业规划等服务。",
                    "priority": "medium"
                })
    
    # 基于核心诉求分析商机
    if "养老规划" in core_needs:
        opportunities.append({
            "type": "养老规划",
            "description": "客户有养老规划诉求，可推荐海外养老签证、医疗保险等服务。",
            "priority": "medium"
        })
    
    if "税务优化" in core_needs:
        opportunities.append({
            "type": "税务咨询",
            "description": "客户关注税务优化，可推荐税务架构设计、信托设立等服务。",
            "priority": "high"
        })
    
    # 基于关联人分析转介绍机会
    if related_contacts:
        opportunities.append({
            "type": "转介绍",
            "description": f"客户有 {len(related_contacts)} 位关联人，可挖掘转介绍机会。",
            "priority": "medium"
        })
    
    # 默认商机
    if not opportunities:
        opportunities.append({
            "type": "深度服务",
            "description": "建议深入了解客户需求，提供定制化服务方案。",
            "priority": "low"
        })
    
    return {
        "report": report,
        "opportunities": opportunities
    }


# ============ 生日祝福工作流 ============

async def generate_birthday_greeting_via_coze(
    name: str,
    birthday_date: str,
    job_type: str = "",
    job_title: str = "",
    style: str = "商务专业"
) -> str:
    """
    调用 Coze 生日祝福工作流生成个性化祝福语
    
    Args:
        name: 客户姓名
        birthday_date: 生日日期 (YYYY-MM-DD)
        job_type: 职业类型
        job_title: 职位/职称
        style: 祝福风格 (商务专业/温馨亲切/幽默风趣/长辈尊享)
    
    Returns:
        生成的祝福语文本
    """
    # 如果未配置 Coze API 或生日工作流 ID，返回模拟祝福
    if not settings.COZE_API_KEY or not settings.COZE_BIRTHDAY_WORKFLOW_ID:
        logger.info("未配置 Coze 生日工作流，使用模拟祝福")
        return _generate_mock_birthday_greeting(name, birthday_date, job_type, job_title, style)
    
    # 构建请求参数 - 直接传入5个独立的 Object 类型参数
    # Coze Workflow 期望的参数: name, job_title, job_type, style, birthday_date (都是 Object 类型)
    # 根据 Coze Object 类型要求，将每个值包装成一个对象
    workflow_input = {
        "name": {"value": name},
        "job_title": {"value": job_title} if job_title else {"value": ""},
        "job_type": {"value": job_type} if job_type else {"value": ""},
        "style": {"value": style},
        "birthday_date": {"value": birthday_date}
    }
    
    request_url = f"{settings.COZE_API_BASE_URL}/workflow/run"
    request_body = {
        "workflow_id": settings.COZE_BIRTHDAY_WORKFLOW_ID,
        "parameters": workflow_input
    }
    
    print("\n" + "="*60)
    print("🎂 [COZE API] 发送生日祝福请求")
    print("="*60)
    print(f"📍 请求地址: {request_url}")
    print(f"📋 Workflow ID: {settings.COZE_BIRTHDAY_WORKFLOW_ID}")
    print(f"📦 发送参数 (parameters):")
    print(json.dumps(workflow_input, ensure_ascii=False, indent=2))
    print("-"*60)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                request_url,
                headers={
                    "Authorization": f"Bearer {settings.COZE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            
            print(f"📊 响应状态码: {response.status_code}")
            
            raw_text = response.text
            print(f"📄 响应体:")
            print("-"*40)
            try:
                formatted = json.dumps(json.loads(raw_text), ensure_ascii=False, indent=2)
                print(formatted[:1000])
            except:
                print(raw_text[:1000])
            print("-"*40)
            
            response.raise_for_status()
            
            result = response.json()
            greeting = _parse_birthday_greeting_response(result)
            
            print(f"✅ 解析成功，祝福语长度: {len(greeting)} 字符")
            print("="*60 + "\n")
            
            return greeting
            
    except httpx.TimeoutException:
        logger.error("Coze 生日工作流请求超时")
        print("❌ 请求超时")
        raise Exception("Coze 生日工作流请求超时，请稍后重试")
    except httpx.HTTPStatusError as e:
        logger.error(f"Coze 生日工作流 HTTP 错误: {e.response.status_code}")
        print(f"❌ HTTP 错误: {e.response.status_code}")
        raise Exception(f"Coze 生日工作流 HTTP 错误: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Coze 生日工作流异常: {str(e)}")
        print(f"❌ API 异常: {str(e)}")
        raise


def _parse_birthday_greeting_response(result: dict) -> str:
    """
    解析 Coze 生日祝福工作流返回结果
    
    兼容多种返回格式，优先提取 greeting/content/data 字段
    """
    # 检查错误码
    code = result.get("code", 0)
    if code != 0:
        error_msg = result.get("msg", result.get("message", "未知错误"))
        raise Exception(f"Coze API 错误: {error_msg}")
    
    data = result.get("data")
    
    # data 为空时尝试其他字段
    if data is None:
        if "greeting" in result:
            return result["greeting"]
        if "content" in result:
            return result["content"]
        if "output" in result:
            return str(result["output"])
        return ""
    
    # data 是字符串
    if isinstance(data, str):
        # 尝试解析 JSON
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed.get("greeting", parsed.get("content", parsed.get("data", data)))
            return str(parsed)
        except json.JSONDecodeError:
            return data
    
    # data 是字典
    if isinstance(data, dict):
        # 尝试多种字段名
        for key in ["greeting", "content", "data", "output", "text", "message"]:
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, dict):
                    # 递归提取
                    for inner_key in ["greeting", "content", "data", "text"]:
                        if inner_key in val:
                            return str(val[inner_key])
        # 兜底
        return str(data)
    
    return str(data) if data else ""


async def generate_birthday_greeting_stream(
    name: str,
    birthday_date: str,
    job_type: str = "",
    job_title: str = "",
    style: str = "商务专业"
) -> AsyncGenerator[str, None]:
    """
    调用 Coze 生日祝福工作流生成个性化祝福语 - 流式输出版本
    
    使用 SSE (Server-Sent Events) 格式返回流式数据
    
    Args:
        name: 客户姓名
        birthday_date: 生日日期 (YYYY-MM-DD)
        job_type: 职业类型
        job_title: 职位/职称
        style: 祝福风格
    
    Yields:
        SSE 格式的流式数据块
    """
    # 如果未配置 Coze API 或生日工作流 ID，返回错误
    if not settings.COZE_API_KEY or not settings.COZE_BIRTHDAY_WORKFLOW_ID:
        logger.error("未配置 Coze 生日工作流")
        yield f"data: {json.dumps({'type': 'error', 'message': '未配置 Coze 生日工作流'}, ensure_ascii=False)}\n\n"
        return
    
    # 构建请求参数 - 与非流式版本相同的格式
    workflow_input = {
        "name": {"value": name},
        "job_title": {"value": job_title} if job_title else {"value": ""},
        "job_type": {"value": job_type} if job_type else {"value": ""},
        "style": {"value": style},
        "birthday_date": {"value": birthday_date}
    }
    
    # 使用流式 API 端点
    request_url = f"{settings.COZE_API_BASE_URL}/workflow/stream_run"
    request_body = {
        "workflow_id": settings.COZE_BIRTHDAY_WORKFLOW_ID,
        "parameters": workflow_input
    }
    
    print("\n" + "="*60)
    print("🎂 [COZE API] 发送生日祝福流式请求")
    print("="*60)
    print(f"📍 请求地址: {request_url}")
    print(f"📋 Workflow ID: {settings.COZE_BIRTHDAY_WORKFLOW_ID}")
    print(f"📦 发送参数 (parameters):")
    print(json.dumps(workflow_input, ensure_ascii=False, indent=2))
    print("-"*60)
    
    accumulated_content = ""
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                request_url,
                headers={
                    "Authorization": f"Bearer {settings.COZE_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"
                },
                json=request_body
            ) as response:
                print(f"📊 流式响应状态码: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_msg = f"API错误: {response.status_code}"
                    print(f"❌ 流式请求失败: {error_text.decode()}")
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
                    return
                
                # 处理 SSE 流
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # 按行处理 SSE 数据
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        # 处理 SSE 数据行
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue
                            
                            try:
                                data = json.loads(data_str)
                                event_type = data.get("event", data.get("type", ""))
                                
                                # 处理不同类型的事件
                                if event_type == "Message":
                                    message_data = data.get("data", data.get("message", {}))
                                    if isinstance(message_data, str):
                                        try:
                                            message_data = json.loads(message_data)
                                        except:
                                            pass
                                    
                                    content = ""
                                    if isinstance(message_data, dict):
                                        content = message_data.get("content", message_data.get("data", ""))
                                    elif isinstance(message_data, str):
                                        content = message_data
                                    
                                    if content:
                                        accumulated_content += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                                
                                elif event_type in ["Output", "output"]:
                                    output_data = data.get("data", data.get("output", ""))
                                    if isinstance(output_data, str):
                                        try:
                                            output_data = json.loads(output_data)
                                        except:
                                            pass
                                    
                                    content = ""
                                    if isinstance(output_data, dict):
                                        content = output_data.get("data", output_data.get("content", output_data.get("output", "")))
                                    elif isinstance(output_data, str):
                                        content = output_data
                                    
                                    if content:
                                        accumulated_content += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                                
                                elif event_type in ["Done", "done", "Completed", "completed"]:
                                    print("✅ 流式输出完成")
                                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                                
                                elif event_type in ["Error", "error"]:
                                    error_msg = data.get("message", data.get("error", "未知错误"))
                                    print(f"❌ 错误事件: {error_msg}")
                                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
                                
                                else:
                                    # 其他事件，尝试提取内容
                                    content = data.get("content", data.get("data", ""))
                                    if isinstance(content, str) and content:
                                        accumulated_content += content
                                        yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                            
                            except json.JSONDecodeError:
                                # 直接作为文本内容输出
                                if data_str and data_str != "[DONE]":
                                    accumulated_content += data_str
                                    yield f"data: {json.dumps({'type': 'content', 'content': data_str}, ensure_ascii=False)}\n\n"
                
                # 发送最终完成事件
                print(f"📝 总共接收内容长度: {len(accumulated_content)} 字符")
                yield f"data: {json.dumps({'type': 'done', 'full_content': accumulated_content}, ensure_ascii=False)}\n\n"
                
    except httpx.TimeoutException as e:
        print(f"❌ 流式请求超时: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': '请求超时，请稍后重试'}, ensure_ascii=False)}\n\n"
    except Exception as e:
        print(f"❌ 流式请求异常: {type(e).__name__}: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


def _generate_mock_birthday_greeting(
    name: str,
    birthday_date: str,
    job_type: str,
    job_title: str,
    style: str
) -> str:
    """
    生成模拟生日祝福（未配置 Coze API 时使用）
    """
    # 根据风格生成不同模板
    templates = {
        "商务专业": f"""尊敬的{name}先生/女士：

值此生辰之际，谨代表侨慧团队向您致以最诚挚的祝福！

感谢您一直以来对我们的信任与支持。愿新的一岁，您的事业蒸蒸日上，身体健康，阖家幸福！

期待在未来的日子里，继续为您提供专业、贴心的服务。

祝：生日快乐！万事如意！

——侨慧·本地CRM""",

        "温馨亲切": f"""亲爱的{name}：

🎂 生日快乐！

今天是属于您的特别日子！愿这一年里，所有的美好都与您相伴，所有的梦想都能实现。

感谢您对我们的信任，能够成为您的朋友，是我们的荣幸。

愿您生日愉快，天天开心！🎉

——您的朋友""",

        "幽默风趣": f"""Hi {name}！

听说今天有个人要"长大"一岁了？别担心，年龄只是个数字，心态年轻才是真的年轻！😄

祝你生日快乐！继续保持那股冲劲儿，今年的小目标：赚它一个亿（的快乐）！

记得今天多吃点蛋糕，反正热量不算数！🎂

生日快乐！ 🎊""",

        "长辈尊享": f"""尊敬的{name}先生/女士：

恭祝您福寿安康，生辰愉快！

岁月如歌，您的智慧与阅历令人敬佩。值此吉日，衷心祝愿您：

福如东海长流水，
寿比南山不老松。

愿您身体康健、心情舒畅、阖家团圆、幸福美满！

谨致崇高的敬意与美好的祝福！

——侨慧团队 敬上"""
    }
    
    return templates.get(style, templates["商务专业"])

