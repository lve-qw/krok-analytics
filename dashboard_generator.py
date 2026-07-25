import pandas as pd
from pathlib import Path
import json

def generate_dashboard(analytics_csv: Path, output_html: Path = None):
    """
    Генерирует Dashboard с интерактивными графиками (plotly.js)
    """
    if output_html is None:
        output_html = analytics_csv.parent / "report.html"
    
    df = pd.read_csv(analytics_csv)
    output_path = Path(output_html)
    
    # ===== Метрики =====
    total_dialogs = len(df)
    total_users = df['user_id'].nunique()
    date_min = df['created_at'].min()
    date_max = df['created_at'].max()
    
    total_tokens = df['total_tokens'].sum()
    avg_tokens = df['total_tokens'].mean()
    total_burned = df['burned_tokens'].sum()
    burned_ratio = (total_burned / total_tokens * 100) if total_tokens > 0 else 0
    total_cost = df['estimated_cost'].sum()
    
    useful_total = df['useful_messages'].sum()
    useless_total = df['useless_messages'].sum()
    useful_ratio = (useful_total / (useful_total + useless_total) * 100) if (useful_total + useless_total) > 0 else 0
    dialogs_with_burned = (df['burned_tokens'] > 0).sum()
    avg_burned_failed = df[df['burned_tokens'] > 0]['burned_tokens'].mean() if dialogs_with_burned > 0 else 0
    
    work_dialogs = (df['is_work'] == True).sum()
    work_ratio = (work_dialogs / total_dialogs * 100) if total_dialogs > 0 else 0
    automation_candidates = (df['automation_candidate'] == True).sum()
    automation_ratio = (automation_candidates / total_dialogs * 100) if total_dialogs > 0 else 0
    
    complexity_dist = df['complexity'].value_counts().to_dict()
    periodicity_dist = df['periodicity'].value_counts().to_dict()
    
    dialogs_with_int = (df['integration_count'] > 0).sum()
    df['integrations'] = df['integrations'].fillna('').astype(str)
    unique_integrations = set()
    df['integrations'].apply(lambda x: unique_integrations.update(x.split(';')) if x and x != 'nan' else None)
    unique_integrations.discard('')
    
    df['tools'] = df['tools'].fillna('').astype(str)
    unique_tools = set()
    df['tools'].apply(lambda x: unique_tools.update(x.split(';')) if x and x != 'nan' else None)
    unique_tools.discard('')
    avg_tool_calls = df['tool_calls'].mean()
    
    total_clusters = (df['cluster_id'] != -1).sum()
    outliers = (df['cluster_id'] == -1).sum()
    cluster_sizes = df.groupby('cluster_id')['member_count'].first()
    top_5_clusters = cluster_sizes.nlargest(5)
    avg_cluster_size = df['member_count'].mean() if len(df) > 0 else 0
    
    agent_failures = (df['agent_failed'] == True).sum()
    failure_reasons = df[df['agent_failed'] == True]['failure_reason'].value_counts().head(5).to_dict()
    prompt_injections = (df['prompt_injection'] == True).sum()
    sensitive_data = (df['contains_sensitive_data'] == True).sum()
    
    lang_dist = df['language'].value_counts().to_dict()
    avg_confidence = df['confidence'].mean()
    low_confidence = (df['confidence'] < 0.5).sum()
    
    top_users = df['user_id'].value_counts().head(10).to_dict()
    
    df['date'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d')
    dialogs_by_date = df.groupby('date').size().to_dict()
    
    integration_counts = {}
    for integrations in df['integrations']:
        if integrations and integrations != 'nan':
            for intr in integrations.split(';'):
                if intr and intr != 'nan':
                    integration_counts[intr] = integration_counts.get(intr, 0) + 1
    top_integrations = dict(sorted(integration_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    
    tool_counts = {}
    for tools in df['tools']:
        if tools and tools != 'nan':
            for tool in tools.split(';'):
                if tool and tool != 'nan':
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1
    top_tools = dict(sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    
    print("Генерация dashboard...")
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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
        .chart-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .chart {{ background: #fafafa; border-radius: 8px; padding: 15px; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>📊 Analytics Dashboard</h1>
    
    <div class="section">
        <h2>Общая статистика</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Диалогов</h3><div class="value">{total_dialogs:,}</div></div>
            <div class="metric-card"><h3>Пользователей</h3><div class="value">{total_users:,}</div></div>
            <div class="metric-card"><h3>Период</h3><div class="value" style="font-size:16px;">{date_min}</div><div class="subtitle">- {date_max}</div></div>
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
        <div class="chart"><div id="tokens_hist"></div></div>
    </div>
    
    <div class="section">
        <h2>Качество агента</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Полезные</h3><div class="value">{useful_total:,}</div></div>
            <div class="metric-card"><h3>Бесполезные</h3><div class="value">{useless_total:,}</div></div>
            <div class="metric-card"><h3>Useful ratio</h3><div class="value">{useful_ratio:.1f}%</div></div>
            <div class="metric-card"><h3>С ошибками</h3><div class="value">{dialogs_with_burned:,}</div></div>
        </div>
        <div class="chart"><div id="useful_chart"></div></div>
    </div>
    
    <div class="section">
        <h2>Классификация</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Рабочие</h3><div class="value">{work_dialogs:,}</div><div class="subtitle">{work_ratio:.1f}%</div></div>
            <div class="metric-card"><h3>Автоматизация</h3><div class="value">{automation_candidates:,}</div><div class="subtitle">{automation_ratio:.1f}%</div></div>
        </div>
        <div class="chart-row">
            <div class="chart"><div id="complexity_chart"></div></div>
            <div class="chart"><div id="periodicity_chart"></div></div>
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
            <div class="chart"><div id="integrations_chart"></div></div>
            <div class="chart"><div id="tools_chart"></div></div>
        </div>
    </div>
    
    <div class="section">
        <h2>Use Cases (кластеры)</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>В кластерах</h3><div class="value">{total_clusters:,}</div></div>
            <div class="metric-card"><h3>Выбросы</h3><div class="value">{outliers:,}</div></div>
            <div class="metric-card"><h3>Средний размер</h3><div class="value">{avg_cluster_size:.1f}</div></div>
        </div>
        <div class="chart"><div id="clusters_chart"></div></div>
    </div>
    
    <div class="section">
        <h2>Проблемы</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Провалы агента</h3><div class="value">{agent_failures:,}</div></div>
            <div class="metric-card"><h3>Промпт-инъекции</h3><div class="value">{prompt_injections:,}</div></div>
            <div class="metric-card"><h3>Чувствительные данные</h3><div class="value">{sensitive_data:,}</div></div>
        </div>
        <div class="chart"><div id="failure_chart"></div></div>
    </div>
    
    <div class="section">
        <h2>Языки</h2>
        <div class="chart" style="max-width:500px;margin:0 auto;"><div id="lang_chart"></div></div>
    </div>
    
    <div class="section">
        <h2>Уверенность классификации</h2>
        <div class="metrics-grid">
            <div class="metric-card"><h3>Средняя confidence</h3><div class="value">{avg_confidence:.3f}</div></div>
            <div class="metric-card"><h3>Низкая (&lt;0.5)</h3><div class="value">{low_confidence:,}</div></div>
        </div>
        <div class="chart"><div id="confidence_chart"></div></div>
    </div>
    
    <div class="section">
        <h2>Топ пользователей</h2>
        <div class="chart"><div id="users_chart"></div></div>
    </div>
    
    <div class="section">
        <h2>Активность по датам</h2>
        <div class="chart"><div id="date_chart"></div></div>
    </div>
    
    <div class="footer">Generated from {analytics_csv.name} | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</div>
    
    <script>
        const tokensHist = {json.dumps(df['total_tokens'].tolist())};
        Plotly.newPlot('tokens_hist', {{
            data: [{{type: 'histogram', x: tokensHist, nbinsx: 50, marker: {{color: '#007bff', opacity: 0.7}}}}],
            layout: {{title: 'Распределение токенов по диалогам', xaxis: {{title: 'Токены'}}, yaxis: {{title: 'Количество'}}, showlegend: false, margin: {{t: 40, b: 40, l: 40, r: 20}}}}
        }});
        
        Plotly.newPlot('useful_chart', {{
            data: [
                {{type: 'bar', x: ['Useful', 'Useless'], y: [{useful_total}, {useless_total}], marker: {{color: ['#28a745', '#dc3545']}}}}
            ],
            layout: {{title: 'Полезные vs Бесполезные сообщения', yaxis: {{title: 'Количество'}}, showlegend: false, margin: {{t: 40, b: 40, l: 40, r: 20}}}}
        }});
        
        Plotly.newPlot('complexity_chart', {{
            data: [{{type: 'pie', labels: {json.dumps(list(complexity_dist.keys()))}, values: {json.dumps(list(complexity_dist.values()))}, marker: {{colors: ['#28a745', '#ffc107', '#dc3545']}}}}],
            layout: {{title: 'Сложность диалогов', margin: {{t: 40, b: 20, l: 20, r: 20}}}}
        }});
        
        Plotly.newPlot('periodicity_chart', {{
            data: [{{type: 'pie', labels: {json.dumps(list(periodicity_dist.keys()))}, values: {json.dumps(list(periodicity_dist.values()))}, marker: {{colors: ['#007bff', '#6f42c1', '#20c997', '#fd7e14']}}}}],
            layout: {{title: 'Периодичность', margin: {{t: 40, b: 20, l: 20, r: 20}}}}
        }});
        
        Plotly.newPlot('integrations_chart', {{
            data: [{{type: 'bar', x: {json.dumps(list(top_integrations.keys()))}, y: {json.dumps(list(top_integrations.values()))}, marker: {{color: '#6f42c1'}}, orientation: 'v'}}],
            layout: {{title: 'Топ-10 интеграций', xaxis: {{title: 'Интеграция', tickangle: -45}}, yaxis: {{title: 'Количество'}}, showlegend: false, margin: {{t: 40, b: 80, l: 40, r: 20}}}}
        }});
        
        Plotly.newPlot('tools_chart', {{
            data: [{{type: 'bar', x: {json.dumps(list(top_tools.keys()))}, y: {json.dumps(list(top_tools.values()))}, marker: {{color: '#20c997'}}, orientation: 'v'}}],
            layout: {{title: 'Топ-10 инструментов', xaxis: {{title: 'Инструмент', tickangle: -45}}, yaxis: {{title: 'Количество'}}, showlegend: false, margin: {{t: 40, b: 80, l: 40, r: 20}}}}
        }});
        
        const clusterLabels = {json.dumps([f'Cluster {i+1}' for i in range(len(top_5_clusters))])};
        const clusterValues = {json.dumps(top_5_clusters.values.tolist())};
        Plotly.newPlot('clusters_chart', {{
            data: [{{type: 'bar', x: clusterLabels, y: clusterValues, marker: {{color: '#fd7e14'}}}}],
            layout: {{title: 'Топ-5 кластеров по размеру', xaxis: {{title: 'Кластер'}}, yaxis: {{title: 'Диалогов'}}, showlegend: false, margin: {{t: 40, b: 40, l: 40, r: 20}}}}
        }});
        
        Plotly.newPlot('failure_chart', {{
            data: [{{type: 'bar', x: {json.dumps(list(failure_reasons.keys()))}, y: {json.dumps(list(failure_reasons.values()))}, marker: {{color: '#dc3545'}}}}],
            layout: {{title: 'Причины провалов агента', xaxis: {{title: 'Причина', tickangle: -45}}, yaxis: {{title: 'Количество'}}, showlegend: false, margin: {{t: 40, b: 80, l: 40, r: 20}}}}
        }});
        
        Plotly.newPlot('lang_chart', {{
            data: [{{type: 'pie', labels: {json.dumps(list(lang_dist.keys()))}, values: {json.dumps(list(lang_dist.values()))}, marker: {{colors: ['#007bff', '#dc3545']}}}}],
            layout: {{title: 'Языки диалогов', margin: {{t: 40, b: 20, l: 20, r: 20}}}}
        }});
        
        const confHist = {json.dumps(df['confidence'].tolist())};
        Plotly.newPlot('confidence_chart', {{
            data: [{{type: 'histogram', x: confHist, nbinsx: 20, marker: {{color: '#ffc107', opacity: 0.7}}}}],
            layout: {{title: 'Распределение уверенности классификации', xaxis: {{title: 'Confidence (0-1)'}}, yaxis: {{title: 'Количество'}}, showlegend: false, margin: {{t: 40, b: 40, l: 40, r: 20}}}}
        }});
        
        Plotly.newPlot('users_chart', {{
            data: [{{type: 'bar', x: {json.dumps(list(top_users.keys()))}, y: {json.dumps(list(top_users.values()))}, marker: {{color: '#007bff'}}, orientation: 'v'}}],
            layout: {{title: 'Топ-10 пользователей', xaxis: {{title: 'Пользователь', tickangle: -45}}, yaxis: {{title: 'Диалогов'}}, showlegend: false, margin: {{t: 40, b: 80, l: 40, r: 20}}}}
        }});
        
        const dates = {json.dumps(list(dialogs_by_date.keys()))};
        const dateValues = {json.dumps(list(dialogs_by_date.values()))};
        Plotly.newPlot('date_chart', {{
            data: [{{type: 'scatter', x: dates, y: dateValues, mode: 'lines+markers', line: {{color: '#007bff', width: 2}, marker: {{size: 6}}}}],
            layout: {{title: 'Активность по датам', xaxis: {{title: 'Дата', tickangle: -45}}, yaxis: {{title: 'Диалоги'}}, showlegend: false, margin: {{t: 40, b: 80, l: 40, r: 20}}}}
        }});
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard сохранён: {output_html}")
    return output_path


if __name__ == "__main__":
    analytics_path = Path("outputs/analytics.csv")
    if analytics_path.exists():
        generate_dashboard(analytics_path)
    else:
        print(f"Файл {analytics_path} не найден.")
