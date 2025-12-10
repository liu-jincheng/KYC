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
    asset_level = kyc_data.get("asset_level", "")
    timeline = kyc_data.get("timeline", "")
    
    # 生成报告
    countries_text = "、".join(target_countries) if target_countries else "未指定"
    needs_text = "、".join(core_needs) if core_needs else "未指定"
    
    report = f"""# {name} 移民方案分析报告

## 一、客户画像

- **意向国家**: {countries_text}
- **核心诉求**: {needs_text}
- **资产级别**: {asset_level or "未知"}
- **办理周期**: {timeline or "未指定"}
- **家庭情况**: {children_count} 位子女

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

