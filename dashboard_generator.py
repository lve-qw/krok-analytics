import pandas as pd
from pathlib import Path

def generate_dashboard(analytics_csv: Path, output_html: Path = None):
    """
    Генерирует Dashboard с графиками на основе метрик из analytics.csv
    Сохраняет в HTML файл
    """
    if output_html is None:
        output_html = analytics_csv.parent / "report.html"
    
    df = pd.read_csv(analytics_csv)
    
    # ===== Основные метрики =====
    total_dialogs = len(df)
    total_users = df['user_id'].nunique()
    date_min = df['created_at'].min()
    date_max = df['created_at'].max()
    
    # ===== Токены =====
    total_tokens = df['total_tokens'].sum()
    avg_tokens = df['total_tokens'].mean()
    total_burned = df['burned_tokens'].sum()
    burned_ratio = (total_burned / total_tokens * 100) if total_tokens > 0 else 0
    total_cost = df['estimated_cost'].sum()
    
    # ===== Качество агента =====
    useful_total = df['useful_messages'].sum()
    useless_total = df['useless_messages'].sum()
    useful_ratio = (useful_total / (useful_total + useless_total) * 100) if (useful_total + useless_total) > 0 else 0
    dialogs_with_burned = (df['burned_tokens'] > 0).sum()
    avg_burned_failed = df[df['burned_tokens'] > 0]['burned_tokens'].mean() if dialogs_with_burned > 0 else 0
    
    # ===== Классификация =====
    work_dialogs = (df['is_work'] == True).sum()
    work_ratio = (work_dialogs / total_dialogs * 100) if total_dialogs > 0 else 0
    automation_candidates = (df['automation_candidate'] == True).sum()
    automation_ratio = (automation_candidates / total_dialogs * 100) if total_dialogs > 0 else 0
    
    # ===== Сложность =====
    complexity_dist = df['complexity'].value_counts().to_dict()
    periodicity_dist = df['periodicity'].value_counts().to_dict()
    
    # ===== Интеграции =====
    dialogs_with_int = (df['integration_count'] > 0).sum()
    unique_integrations = set()
    df['integrations'] = df['integrations'].fillna('').astype(str)
    df['integrations'].apply(lambda x: unique_integrations.update(x.split(';')) if x and x != 'nan' else None)
    unique_integrations.discard('')
    
    unique_tools = set()
    df['tools'] = df['tools'].fillna('').astype(str)
    df['tools'].apply(lambda x: unique_tools.update(x.split(';')) if x and x != 'nan' else None)
    unique_tools.discard('')
    
    avg_tool_calls = df['tool_calls'].mean()
    
    # ===== Use Cases =====
    total_clusters = (df['cluster_id'] != -1).sum()
    outliers = (df['cluster_id'] == -1).sum()
    cluster_sizes = df.groupby('cluster_id')['member_count'].first()
    top_5_clusters = cluster_sizes.nlargest(5)
    avg_cluster_size = df['member_count'].mean() if len(df) > 0 else 0
    
    # ===== Проблемы =====
    agent_failures = (df['agent_failed'] == True).sum()
    failure_reasons = df[df['agent_failed'] == True]['failure_reason'].value_counts().head(5).to_dict()
    prompt_injections = (df['prompt_injection'] == True).sum()
    sensitive_data = (df['contains_sensitive_data'] == True).sum()
    
    # ===== Языки =====
    lang_dist = df['language'].value_counts().to_dict()
    
    # ===== Уверенность =====
    avg_confidence = df['confidence'].mean()
    low_confidence = (df['confidence'] < 0.5).sum()
    
    # ===== Топ пользователи =====
    top_users = df['user_id'].value_counts().head(10)
    
    # ===== Диалоги по датам =====
    df['date'] = pd.to_datetime(df['created_at']).str[:10]
    dialogs_by_date = df.groupby('date').size().tail(30)
    
    # ===== Топ интеграций =====
    integration_counts = {}
    for integrations in df['integrations']:
        if integrations and integrations != 'nan':
            for intr in integrations.split(';'):
                if intr and intr != 'nan':
                    integration_counts[intr] = integration_counts.get(intr, 0) + 1
    top_integrations = sorted(integration_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # ===== Топ инструментов =====
    tool_counts = {}
    for tools in df['tools']:
        if tools and tools != 'nan':
            for tool in tools.split(';'):
                if tool and tool != 'nan':
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1
    top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    def bar_chart(values, labels, title, color='#007bff', height=200):
        """Генерирует простой bar chart в SVG."""
        if not values or sum(values) == 0:
            return f'<div class="chart"><h4>{title}</h4><p>Нет данных</p></div>'
        
        max_val = max(values) if values else 1
        bar_height = height - 40
        chart_width = max(300, len(values) * 60)
        
        bars = []
        for i, (val, label) in enumerate(zip(values, labels)):
            bar_h = (val / max_val * bar_height) if max_val > 0 else 0
            x = i * 60 + 10
            bars.append(f'<rect x="{x}" y="{height - bar_h - 30}" width="50" height="{bar_h}" fill="{color}"/><text x="{x + 25}" y="{height - 15}" font-size="10" text-anchor="middle">{str(label)[:10]}</text><text x="{x + 25}" y="{height - bar_h - 35}" font-size="11" text-anchor="middle" font-weight="bold">{val}</text>')
        
        svg = f'<svg width="{chart_width}" height="{height + 20}">' + ''.join(bars) + f'<text x="{chart_width/2}" y="{height + 15}" font-size="12" text-anchor="middle" font-weight="bold">{title}</text></svg>'
        return f'<div class="chart">{svg}</div>'
    
    def pie_chart(values, labels, title):
        """Генерирует pie chart в SVG."""
        if not values or sum(values) == 0:
            return f'<div class="chart"><h4>{title}</h4><p>Нет данных</p></div>'
        
        colors = ['#007bff', '#28a745', '#dc3545', '#ffc107', '#6f42c1', '#20c997', '#fd7e14', '#e83e8c']
        total = sum(values)
        
        slices = []
        start_angle = 0
        for i, (val, label) in enumerate(zip(values, labels)):
            angle = val / total * 360
            end_angle = start_angle + angle
            
            # Конвертируем углы в координаты
            import math
            x1 = 100 + 80 * math.cos(math.radians(start_angle - 90))
            y1 = 100 + 80 * math.sin(math.radians(start_angle - 90))
            x2 = 100 + 80 * math.cos(math.radians(end_angle - 90))
            y2 = 100 + 80 * math.sin(math.radians(end_angle - 90))
            
            large_arc = 1 if angle > 180 else 0
            path = f'M 100 100 L {x1:.1f} {y1:.1f} A 80 80 0 {large_arc} 1 {x2:.1f} {y2:.1f} Z'
            
            color = colors[i % len(colors)]
            slices.append(f'<path d="{path}" fill="{color}" stroke="white" stroke-width="1"><title>{label}: {val} ({val/total*100:.1f}%)</title></path>')
            
            start_angle = end_angle
        
        legend = ''.join([f'<div style="display:inline-block;margin:5px;"><span style="display:inline-block;width:12px;height:12px;background:{colors[i % len(colors)]};margin-right:5px;"></span>{label}: {val}</div>' for i, (label, val) in enumerate(zip(labels, values))])
        
        svg = f'<svg width="220" height="200"><circle cx="100" cy="100" r="80" fill="none"/>' + ''.join(slices) + '</svg>'
        return f'<div class="chart"><h4>{title}</h4><div style="display:flex;align-items:center;justify-content:center;">{svg}<div style="margin-left:20px;font-size:12px;">{legend}</div></div></div>'
    
    def progress_bar(value, total, label, color='#007bff'):
        """Генерирует progress bar."""
        pct = (value / total * 100) if total > 0 else 0
        return f'<div class="metric"><span>{label}</span><div class="progress"><div class="progress-bar" style="width:{pct}%;background:{color}"></div></div><span>{value:,} / {total:,} ({pct:.1f}%)</span></div>'
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics Dashboard</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        h1 {{ text-align: center; color: #333; margin-bottom: 30px; }}
        h2 {{ color: #444; border-bottom: 2px solid #007bff; padding-bottom: 10px; margin: 30px 0 20px 0; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .metric-card h3 {{ font-size: 13px; color: #666; margin-bottom: 10px; font-weight: normal; }}
        .metric-card .value {{ font-size: 28px; font-weight: bold; color: #333; }}
        .metric-card .subtitle {{ font-size: 12px; color: #999; margin-top: 5px; }}
        .section {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }}
        .chart-row {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }}
        .chart {{ background: #fafafa; border-radius: 8px; padding: 15px; margin: 10px; }}
        .chart h4 {{ text-align: center; margin-bottom: 10px; color: #555; }}
        .metric {{ margin: 10px 0; }}
        .metric span {{ display: block; font-size: 14px; color: #555; margin-bottom: 5px; }}
        .progress {{ background: #e9ecef; border-radius: 4px; height: 20px; overflow: hidden; margin: 5px 0; }}
        .progress-bar {{ height: 100%; transition: width 0.3s; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 12px; }}
        svg {{ max-width: 100%; }}
    </style>
</head>
<body>
    <h1>📊 Analytics Dashboard</h1>
    
    <div class="section">
        <h2>Общая статистика</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Диалогов</h3><div class="value">{total_dialogs:,}</div></div>
            <div class="metric-card"><h3>Пользователей</h3><div class="value">{total_users:,}</div></div>
            <div class="metric-card"><h3>Период</h3><div class="value" style="font-size:16px;">{date_min[:10] if date_min else 'N/A'}</div><div class="subtitle">- {date_max[:10] if date_max else 'N/A'}</div></div>
        </div>
    </div>
    
    <div class="section">
        <h2>Токены и стоимость</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Всего токенов</h3><div class="value">{total_tokens:,}</div></div>
            <div class="metric-card"><h3>Среднее на диалог</h3><div class="value">{avg_tokens:,.0f}</div></div>
            <div class="metric-card"><h3>Burned tokens</h3><div class="value">{total_burned:,}</div><div class="subtitle">{burned_ratio:.2f}%</div></div>
            <div class="metric-card"><h3>Стоимость</h3><div class="value">${total_cost:.2f}</div></div>
        </div>
        {bar_chart([total_tokens, total_burned], ['Total', 'Burned'], 'Tokens Overview', '#007bff', 150)}
    </div>
    
    <div class="section">
        <h2>Качество агента</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Полезные</h3><div class="value">{useful_total:,}</div></div>
            <div class="metric-card"><h3>Бесполезные</h3><div class="value">{useless_total:,}</div></div>
            <div class="metric-card"><h3>Useful ratio</h3><div class="value">{useful_ratio:.1f}%</div></div>
            <div class="metric-card"><h3>С ошибками</h3><div class="value">{dialogs_with_burned:,}</div></div>
        </div>
        <div class="metric">
            <span>Useful / Useless</span>
            <div class="progress"><div class="progress-bar" style="width:{useful_ratio}%;background:#28a745"></div></div>
            <span>{useful_ratio:.1f}% полезных сообщений</span>
        </div>
    </div>
    
    <div class="section">
        <h2>Классификация</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Рабочие</h3><div class="value">{work_dialogs:,}</div><div class="subtitle">{work_ratio:.1f}%</div></div>
            <div class="metric-card"><h3>Автоматизация</h3><div class="value">{automation_candidates:,}</div><div class="subtitle">{automation_ratio:.1f}%</div></div>
        </div>
        <div class="chart-row">
            {pie_chart(list(complexity_dist.values()), list(complexity_dist.keys()), 'Сложность')}
            {pie_chart(list(periodicity_dist.values()), list(periodicity_dist.keys()), 'Периодичность')}
        </div>
    </div>
    
    <div class="section">
        <h2>Интеграции и инструменты</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>С интеграциями</h3><div class="value">{dialogs_with_int:,}</div></div>
            <div class="metric-card"><h3>Уник. интеграции</h3><div class="value">{len(unique_integrations)}</div></div>
            <div class="metric-card"><h3>Уник. инструменты</h3><div class="value">{len(unique_tools)}</div></div>
            <div class="metric-card"><h3>Среднее tool calls</h3><div class="value">{avg_tool_calls:.1f}</div></div>
        </div>
        <div class="chart-row">
            {bar_chart([v for v in top_integrations[:5]], [l for l, _ in top_integrations[:5]], 'Топ интеграций', '#6f42c1', 180)}
            {bar_chart([v for v in top_tools[:5]], [l for l, _ in top_tools[:5]], 'Топ инструментов', '#20c997', 180)}
        </div>
    </div>
    
    <div class="section">
        <h2>Use Cases (кластеры)</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>В кластерах</h3><div class="value">{total_clusters:,}</div></div>
            <div class="metric-card"><h3>Выбросы</h3><div class="value">{outliers:,}</div></div>
            <div class="metric-card"><h3>Средний размер</h3><div class="value">{avg_cluster_size:.1f}</div></div>
        </div>
        {bar_chart(top_5_clusters.values.tolist(), [f'C{i+1}' for i in range(len(top_5_clusters))], 'Топ-5 кластеров', '#fd7e14', 180)}
    </div>
    
    <div class="section">
        <h2>Проблемы</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Провалы агента</h3><div class="value">{agent_failures:,}</div></div>
            <div class="metric-card"><h3>Промпт-инъекции</h3><div class="value">{prompt_injections:,}</div></div>
            <div class="metric-card"><h3>Чувствительные данные</h3><div class="value">{sensitive_data:,}</div></div>
        </div>
        {bar_chart(list(failure_reasons.values()), list(failure_reasons.keys()), 'Причины провалов', '#dc3545', 180)}
    </div>
    
    <div class="section">
        <h2>Языки</h2>
        {pie_chart(list(lang_dist.values()), list(lang_dist.keys()), 'Распределение языков')}
    </div>
    
    <div class="section">
        <h2>Уверенность классификации</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Средняя confidence</h3><div class="value">{avg_confidence:.3f}</div></div>
            <div class="metric-card"><h3>Низкая (&lt;0.5)</h3><div class="value">{low_confidence:,}</div></div>
        </div>
    </div>
    
    <div class="section">
        <h2>Топ пользователей</h2>
        {bar_chart(top_users.values.tolist(), [u[:15] for u in top_users.index], 'Диалоги по пользователям', '#007bff', 200)}
    </div>
    
    <div class="footer">Generated from {analytics_csv.name} | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard сохранён: {output_html}")
    return output_path


if __name__ == "__main__":
    analytics_path = Path("outputs/analytics.csv")
    if analytics_path.exists():
        generate_dashboard(analytics_path)
    else:
        print(f"Файл {analytics_path} не найден. Запустите main.py сначала.")
