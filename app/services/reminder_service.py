"""
提醒引擎服务
"""
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Customer, CustomerStatus
from app.schemas import DashboardReminders, ReminderItem


def get_all_reminders(db: Session) -> DashboardReminders:
    """
    获取所有待办提醒
    
    - 跟进提醒: next_follow_up <= today 的客户
    - 生日提醒: 仅当 birthday 字段非空时计算(7天内生日)
    - 状态滞留: 状态为"AI分析中"超过3天的客户
    """
    today = date.today()
    
    follow_ups = _get_follow_up_reminders(db, today)
    birthdays = _get_birthday_reminders(db, today)
    stale_analyses = _get_stale_analysis_reminders(db, today)
    
    return DashboardReminders(
        follow_ups=follow_ups,
        birthdays=birthdays,
        stale_analyses=stale_analyses
    )


def _get_follow_up_reminders(db: Session, today: date) -> list[ReminderItem]:
    """获取跟进提醒"""
    reminders = []
    
    # 查询 next_follow_up <= today 的客户
    customers = db.query(Customer).filter(
        and_(
            Customer.is_deleted == 0,
            Customer.next_follow_up != None,
            Customer.next_follow_up <= today,
            Customer.status != CustomerStatus.SIGNED.value  # 已签约的不需要提醒
        )
    ).all()
    
    for customer in customers:
        days_overdue = (today - customer.next_follow_up).days
        
        if days_overdue == 0:
            message = "今日需要跟进"
        elif days_overdue > 0:
            message = f"跟进已逾期 {days_overdue} 天"
        else:
            message = f"还有 {-days_overdue} 天需要跟进"
        
        reminders.append(ReminderItem(
            type="follow_up",
            customer_id=customer.id,
            customer_name=customer.name,
            message=message,
            date=customer.next_follow_up
        ))
    
    return reminders


def _get_birthday_reminders(db: Session, today: date) -> list[ReminderItem]:
    """
    获取生日提醒
    仅当 birthday 字段非空时才计算
    返回未来7天内过生日的客户
    """
    reminders = []
    
    # 只查询有生日数据的客户
    customers = db.query(Customer).filter(
        and_(
            Customer.is_deleted == 0,
            Customer.birthday != None
        )
    ).all()
    
    for customer in customers:
        # 计算今年的生日日期
        this_year_birthday = customer.birthday.replace(year=today.year)
        
        # 如果今年生日已过，计算明年生日
        if this_year_birthday < today:
            this_year_birthday = customer.birthday.replace(year=today.year + 1)
        
        # 计算距离生日还有多少天
        days_until_birthday = (this_year_birthday - today).days
        
        # 7天内的生日才提醒
        if 0 <= days_until_birthday <= 7:
            if days_until_birthday == 0:
                message = "🎂 今天生日！"
            elif days_until_birthday == 1:
                message = "🎂 明天生日"
            else:
                message = f"🎂 还有 {days_until_birthday} 天生日"
            
            reminders.append(ReminderItem(
                type="birthday",
                customer_id=customer.id,
                customer_name=customer.name,
                message=message,
                date=this_year_birthday
            ))
    
    return reminders


def _get_stale_analysis_reminders(db: Session, today: date) -> list[ReminderItem]:
    """
    获取状态滞留提醒
    状态为"AI分析中"超过3天的客户
    """
    reminders = []
    
    three_days_ago = datetime.now() - timedelta(days=3)
    
    # 查询状态为"AI分析中"且更新时间超过3天的客户
    customers = db.query(Customer).filter(
        and_(
            Customer.is_deleted == 0,
            Customer.status == CustomerStatus.ANALYZING.value,
            Customer.updated_at < three_days_ago
        )
    ).all()
    
    for customer in customers:
        if customer.updated_at:
            days_stale = (datetime.now() - customer.updated_at).days
            message = f"AI分析已滞留 {days_stale} 天，请检查"
        else:
            message = "AI分析状态异常，请检查"
        
        reminders.append(ReminderItem(
            type="stale",
            customer_id=customer.id,
            customer_name=customer.name,
            message=message,
            date=None
        ))
    
    return reminders

