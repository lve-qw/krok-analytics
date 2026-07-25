import pandas as pd
from pathlib import Path
import json

def generate_dashboard(analytics_csv: Path, output_html: Path = None):
    """
    Генерирует Dashboard с графиками на основе метрик из analytics.csv
    Сохраняет в HTML файл с plotly.js графиками
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
    failure_reasons = df[df['agent_failed'] == True]['failure_reason'].value_counts().head(10).to_dict()
    prompt_injections = (df['prompt_injection'] == True).sum()
    sensitive_data = (df['contains_sensitive_data'] == True).sum()
    
    # ===== Языки =====
    lang_dist = df['language'].value_counts().to_dict()
    
    # ===== Уверенность =====
    avg_confidence = df['confidence'].mean()
    low_confidence = (df['confidence'] < 0.5).sum()
    
    # ===== Данные для графиков =====
    
    # Токены по диалогам (histogram)
    tokens_hist = df['total_tokens'].tolist()
    
    # Burned tokens по диалогам
    burned_hist = df['burned_tokens'].tolist()
    
    # Топ-10 пользователей по количеству диалогов
    top_users = df['user_id'].value_counts().head(10)
    
    # Диалоги по датам
    df['date'] = pd.to_datetime(df['created_at']).dt.date
    dialogs_by_date = df.groupby('date').size()
    
    # Распределение confidence
    confidence_hist = df['confidence'].tolist()
    
    # Топ-10 интеграций
    integration_counts = {}
    for integrations in df['integrations']:
        if integrations:
            for intr in integrations.split(';'):
                if intr and intr != 'nan':
                    integration_counts[intr] = integration_counts.get(intr, 0) + 1
    top_integrations = sorted(integration_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Топ-10 инструментов
    tool_counts = {}
    for tools in df['tools']:
        if tools:
            for tool in tools.split(';'):
                if tool and tool != 'nan':
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1
    top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Распределение по complexity
    complexity_labels = list(complexity_dist.keys())
    complexity_values = list(complexity_dist.values())
    
    # Распределение по periodicity
    periodicity_labels = list(periodicity_dist.keys())
    periodicity_values = list(periodicity_dist.values())
    
    # Топ-5 кластеров
    top5_labels = [f"Cluster {int(cid)}" for cid in top_5_clusters.index]
    top5_values = top_5_clusters.values.tolist()
    
    # Распределение failure_reasons
    failure_labels = list(failure_reasons.keys())[:5]
    failure_values = list(failure_reasons.values())[:5]
    
    # ===== Генерируем HTML с графиками =====
    print(f"Генерация dashboard...")
    
    html_content = f"""
<!DOCTYPE html>
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
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .metric-card h3 {{ font-size: 14px; color: #666; margin-bottom: 10px; font-weight: normal; }}
        .metric-card .value {{ font-size: 28px; font-weight: bold; color: #333; }}
        .metric-card .subtitle {{ font-size: 12px; color: #999; margin-top: 5px; }}
        .chart-container {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }}
        .chart-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .footer {{ text-align: center; color: #999; padding: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>📊 Analytics Dashboard</h1>
    
    <h2>Общая статистика</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Диалогов</h3><div class="value">{total_dialogs:,}</div></div>
        <div class="metric-card"><h3>Пользователей</h3><div class="value">{total_users:,}</div></div>
        <div class="metric-card"><h3>Период</h3><div class="value">{date_min[:10] if date_min else 'N/A'}</div><div class="subtitle">- {date_max[:10] if date_max else 'N/A'}</div></div>
    </div>
    
    <h2>Токены и стоимость</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Всего токенов</h3><div class="value">{total_tokens:,}</div></div>
        <div class="metric-card"><h3>Среднее на диалог</h3><div class="value">{avg_tokens:,.0f}</div></div>
        <div class="metric-card"><h3>Burned tokens</h3><div class="value">{total_burned:,}</div><div class="subtitle">{burned_ratio:.2f}% от общих</div></div>
        <div class="metric-card"><h3>Стоимость</h3><div class="value">${total_cost:.2f}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-container"><div id="tokens_hist"></div></div>
        <div class="chart-container"><div id="burned_hist"></div></div>
    </div>
    
    <h2>Качество агента</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Полезные сообщения</h3><div class="value">{useful_total:,}</div></div>
        <div class="metric-card"><h3>Бесполезные сообщения</h3><div class="value">{useless_total:,}</div></div>
        <div class="metric-card"><h3>Useful ratio</h3><div class="value">{useful_ratio:.1f}%</div></div>
        <div class="metric-card"><h3>Диалоги с ошибками</h3><div class="value">{dialogs_with_burned:,}</div><div class="subtitle">Avg burned: {avg_burned_failed:,.0f}</div></div>
    </div>
    <div class="chart-container"><div id="useful_burned_chart"></div></div>
    
    <h2>Классификация</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Рабочие диалоги</h3><div class="value">{work_dialogs:,}</div><div class="subtitle">{work_ratio:.1f}%</div></div>
        <div class="metric-card"><h3>Кандидаты на автоматизацию</h3><div class="value">{automation_candidates:,}</div><div class="subtitle">{automation_ratio:.1f}%</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-container"><div id="complexity_chart"></div></div>
        <div class="chart-container"><div id="periodicity_chart"></div></div>
    </div>
    
    <h2>Интеграции и инструменты</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Диалоги с интеграциями</h3><div class="value">{dialogs_with_int:,}</div></div>
        <div class="metric-card"><h3>Уникальные интеграции</h3><div class="value">{len(unique_integrations)}</div></div>
        <div class="metric-card"><h3>Уникальные инструменты</h3><div class="value">{len(unique_tools)}</div></div>
        <div class="metric-card"><h3>Среднее tool calls</h3><div class="value">{avg_tool_calls:.1f}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-container"><div id="top_integrations"></div></div>
        <div class="chart-container"><div id="top_tools"></div></div>
    </div>
    
    <h2>Use Cases (кластеры)</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>В кластерах</h3><div class="value">{total_clusters:,}</div></div>
        <div class="metric-card"><h3>Выбросы (outliers)</h3><div class="value">{outliers:,}</div></div>
        <div class="metric-card"><h3>Средний размер кластера</h3><div class="value">{avg_cluster_size:.1f}</div></div>
    </div>
    <div class="chart-container"><div id="top_clusters"></div></div>
    
    <h2>Проблемы</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Провалы агента</h3><div class="value">{agent_failures:,}</div></div>
        <div class="metric-card"><h3>Промпт-инъекции</h3><div class="value">{prompt_injections:,}</div></div>
        <div class="metric-card"><h3>Чувствительные данные</h3><div class="value">{sensitive_data:,}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-container"><div id="failure_reasons"></div></div>
        <div class="chart-container"><div id="language_dist"></div></div>
    </div>
    
    <h2>Уверенность классификации</h2>
    <div class="metrics-grid">
        <div class="metric-card"><h3>Средняя confidence</h3><div class="value">{avg_confidence:.3f}</div></div>
        <div class="metric-card"><h3>Низкая confidence (&lt;0.5)</h3><div class="value">{low_confidence:,}</div></div>
    </div>
    <div class="chart-container"><div id="confidence_hist"></div></div>
    
    <h2>Активность по датам</h2>
    <div class="chart-container"><div id="dialogs_by_date"></div></div>
    
    <div class="footer">Generated from {analytics_csv.name} | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</div>
    
    <script>
        // Tokens histogram
        Plotly.newPlot('tokens_hist', {{
            data: [{{type: 'histogram', x: {json.dumps(tokens_hist)}, name: 'Tokens', marker: {{color: '#007bff'}}}}],
            layout: {{title: 'Распределение токенов по диалогам', xaxis: {{title: 'Токены'}}, yaxis: {{title: 'Количество'}}, showlegend: false}}
        }});
        
        // Burned histogram
        Plotly.newPlot('burned_hist', {{
            data: [{{type: 'histogram', x: {json.dumps(burned_hist)}, name: 'Burned', marker: {{color: '#dc3545'}}}}],
            layout: {{title: 'Распределение burned tokens', xaxis: {{title: 'Burned tokens'}}, yaxis: {{title: 'Количество'}}, showlegend: false}}
        }});
        
        // Useful vs Burned per dialog
        Plotly.newPlot('useful_burned_chart', {{
            data: [
                {{type: 'bar', x: Array.from({{length: {min(50, total_dialogs)}}}, (_, i) => i), y: {json.dumps(df['useful_messages'].head(50).tolist())}, name: 'Useful', marker: {{color: '#28a745'}}}},
                {{type: 'bar', x: Array.from({{length: {min(50, total_dialogs)}}}, (_, i) => i), y: {json.dumps(df['useless_messages'].head(50).tolist())}, name: 'Useless', marker: {{color: '#dc3545'}}}}
            ],
            layout: {{title: 'Полезные vs Бесполезные сообщения (первые 50 диалогов)', barmode: 'group', xaxis: {{title: 'Диалог'}}, yaxis: {{title: 'Сообщения'}}}}
        }});
        
        // Complexity pie
        Plotly.newPlot('complexity_chart', {{
            data: [{{type: 'pie', labels: {json.dumps(complexity_labels)}, values: {json.dumps(complexity_values)}, marker: {{colors: ['#28a745', '#ffc107', '#dc3545']}}}}],
            layout: {{title: 'Сложность диалогов'}}
        }});
        
        // Periodicity pie
        Plotly.newPlot('periodicity_chart', {{
            data: [{{type: 'pie', labels: {json.dumps(periodicity_labels)}, values: {json.dumps(periodicity_values)}, marker: {{colors: ['#007bff', '#6f42c1', '#20c997', '#fd7e14']}}}}],
            layout: {{title: 'Периодичность'}}
        }});
        
        // Top integrations
        Plotly.newPlot('top_integrations', {{
            data: [{{type: 'bar', x: {json.dumps([x[0] for x in top_integrations])}, y: {json.dumps([x[1] for x in top_integrations])}, marker: {{color: '#007bff'}}, orientation: 'v'}}],
            layout: {{title: 'Топ-10 интеграций', xaxis: {{title: 'Интеграция', tickangle: -45}}, yaxis: {{title: 'Количество'}}, showlegend: false}}
        }});
        
        // Top tools
        Plotly.newPlot('top_tools', {{
            data: [{{type: 'bar', x: {json.dumps([x[0] for x in top_tools])}, y: {json.dumps([x[1] for x in top_tools])}, marker: {{color: '#6f42c1'}}, orientation: 'v'}}],
            layout: {{title: 'Топ-10 инструментов', xaxis: {{title: 'Инструмент', tickangle: -45}}, yaxis: {{title: 'Количество'}}, showlegend: false}}
        }});
        
        // Top clusters
        Plotly.newPlot('top_clusters', {{
            data: [{{type: 'bar', x: {json.dumps(top5_labels)}, y: {json.dumps(top5_values)}, marker: {{color: '#20c997'}}}}],
            layout: {{title: 'Топ-5 кластеров по размеру', xaxis: {{title: 'Кластер'}}, yaxis: {{title: 'Диалогов'}}, showlegend: false}}
        }});
        
        // Failure reasons
        Plotly.newPlot('failure_reasons', {{
            data: [{{type: 'bar', x: {json.dumps(failure_labels)}, y: {json.dumps(failure_values)}, marker: {{color: '#dc3545'}}}}],
            layout: {{title: 'Причины провалов агента', xaxis: {{title: 'Причина', tickangle: -45}}, yaxis: {{title: 'Количество'}}, showlegend: false}}
        }});
        
        // Language distribution
        Plotly.newPlot('language_dist', {{
            data: [{{type: 'pie', labels: {json.dumps(list(lang_dist.keys()))}, values: {json.dumps(list(lang_dist.values()))}, marker: {{colors: ['#007bff', '#dc3545']}}}}],
            layout: {{title: 'Языки диалогов'}}
        }});
        
        // Confidence histogram
        Plotly.newPlot('confidence_hist', {{
            data: [{{type: 'histogram', x: {json.dumps(confidence_hist)}, name: 'Confidence', marker: {{color: '#ffc107'}}}}],
            layout: {{title: 'Распределение уверенности классификации', xaxis: {{title: 'Confidence (0-1)'}}, yaxis: {{title: 'Количество'}}, showlegend: false}}
        }});
        
        // Dialogs by date
        Plotly.newPlot('dialogs_by_date', {{
            data: [{{type: 'scatter', x: {json.dumps([str(d) for d in dialogs_by_date.index.tolist()])}, y: {json.dumps(dialogs_by_date.values.tolist())}, mode: 'lines+markers', line: {{color: '#007bff', width: 2}}}}],
            layout: {{title: 'Активность по датам', xaxis: {{title: 'Дата', tickangle: -45}}, yaxis: {{title: 'Диалоги'}}, showlegend: false}}
        }});
    </script>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard сохранён: {output_html}")
    return output_path


if __name__ == "__main__":
    from pathlib import Path
    analytics_path = Path("outputs/analytics.csv")
    if analytics_path.exists():
        generate_dashboard(analytics_path)
    else:
        print(f"Файл {analytics_path} не найден. Запустите main.py сначала.")
