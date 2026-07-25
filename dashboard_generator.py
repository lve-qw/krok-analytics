import pandas as pd
from pathlib import Path
from dash import Dash, html, dash_table
import dash

def generate_dashboard(analytics_csv: Path, output_html: Path = None):
    """
    Генерирует Dash dashboard с метриками из analytics.csv
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
    df['integrations'].fillna('', inplace=True)
    df['integrations'].apply(lambda x: unique_integrations.update(x.split(';')) if x else None)
    unique_integrations.discard('')
    
    unique_tools = set()
    df['tools'].fillna('', inplace=True)
    df['tools'].apply(lambda x: unique_tools.update(x.split(';')) if x else None)
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
    failure_reasons = df[df['agent_failed'] == True]['failure_reason'].value_counts().to_dict()
    prompt_injections = (df['prompt_injection'] == True).sum()
    sensitive_data = (df['contains_sensitive_data'] == True).sum()
    
    # ===== Языки =====
    lang_dist = df['language'].value_counts().to_dict()
    
    # ===== Уверенность =====
    avg_confidence = df['confidence'].mean()
    low_confidence = (df['confidence'] < 0.5).sum()
    
    # ===== Создаём Dashboard =====
    app = Dash(__name__)
    
    def metric_card(title, value, subtitle=None):
        return html.Div([
            html.H4(title, style={'margin': '0 0 10px 0', 'font-size': '14px', 'color': '#666'}),
            html.H3(str(value), style={'margin': '0', 'font-size': '24px'}),
            html.Small(subtitle, style={'color': '#999'}) if subtitle else None
        ], style={
            'padding': '15px',
            'border': '1px solid #ddd',
            'border-radius': '5px',
            'margin': '10px',
            'background': '#fff'
        })
    
    def section(title, children):
        return html.Div([
            html.H3(title, style={'border-bottom': '2px solid #333', 'padding-bottom': '10px'}),
            html.Div(children, style={'display': 'flex', 'flexWrap': 'wrap'})
        ], style={'margin': '20px 0'})
    
    app.layout = html.Div([
        html.H1("Analytics Dashboard", style={'textAlign': 'center', 'margin': '20px'}),
        
        section("Общая статистика", [
            metric_card("Диалогов", total_dialogs),
            metric_card("Пользователей", total_users),
            metric_card("Период", f"{date_min[:10]} - {date_max[:10]}")
        ]),
        
        section("Токены и стоимость", [
            metric_card("Всего токенов", f"{total_tokens:,}"),
            metric_card("Среднее на диалог", f"{avg_tokens:,.0f}"),
            metric_card("Burned tokens", f"{total_burned:,}", f"{burned_ratio:.2f}% от общих"),
            metric_card("Стоимость ($)", f"${total_cost:.2f}")
        ]),
        
        section("Качество агента", [
            metric_card("Полезные сообщения", useful_total),
            metric_card("Бесполезные сообщения", useless_total),
            metric_card("Useful ratio", f"{useful_ratio:.1f}%"),
            metric_card("Диалоги с ошибками", dialogs_with_burned, f"Среднее burned: {avg_burned_failed:.0f}")
        ]),
        
        section("Классификация", [
            metric_card("Рабочие диалоги", work_dialogs, f"{work_ratio:.1f}%"),
            metric_card("Кандидаты на автоматизацию", automation_candidates, f"{automation_ratio:.1f}%")
        ]),
        
        section("Сложность", [
            metric_card("Simple", complexity_dist.get('simple', 0)),
            metric_card("Medium", complexity_dist.get('medium', 0)),
            metric_card("Complex", complexity_dist.get('complex', 0))
        ]),
        
        section("Периодичность", [
            metric_card("None", periodicity_dist.get('none', 0)),
            metric_card("Daily", periodicity_dist.get('daily', 0)),
            metric_card("Weekly", periodicity_dist.get('weekly', 0)),
            metric_card("Monthly", periodicity_dist.get('monthly', 0))
        ]),
        
        section("Интеграции и инструменты", [
            metric_card("Диалоги с интеграциями", dialogs_with_int),
            metric_card("Уникальные интеграции", len(unique_integrations)),
            metric_card("Уникальные инструменты", len(unique_tools)),
            metric_card("Среднее tool calls", f"{avg_tool_calls:.1f}")
        ]),
        
        section("Use Cases (кластеры)", [
            metric_card("В кластерах", total_clusters),
            metric_card("Выбросы (outliers)", outliers),
            metric_card("Средний размер кластера", f"{avg_cluster_size:.1f}"),
            html.Div([
                html.H4("Топ-5 кластеров", style={'margin': '0 0 10px 0', 'font-size': '14px', 'color': '#666'}),
                html.Ul([
                    html.Li(f"Кластер {cid}: {count} диалогов")
                    for cid, count in top_5_clusters.items()
                ])
            ], style={'padding': '15px', 'border': '1px solid #ddd', 'border-radius': '5px', 'margin': '10px'})
        ]),
        
        section("Проблемы", [
            metric_card("Провалы агента", agent_failures),
            metric_card("Промпт-инъекции", prompt_injections),
            metric_card("Чувствительные данные", sensitive_data)
        ]),
        
        section("Языки", [
            metric_card("Russian", lang_dist.get('ru', 0)),
            metric_card("English", lang_dist.get('en', 0))
        ]),
        
        section("Уверенность классификации", [
            metric_card("Средняя confidence", f"{avg_confidence:.3f}"),
            metric_card("Низкая confidence (<0.5)", low_confidence)
        ]),
        
        html.Hr(),
        html.P(f"Generated from {analytics_csv.name}", style={'textAlign': 'center', 'color': '#999'})
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '20px', 'fontFamily': 'Arial'})
    
    # ===== Сохраняем в HTML =====
    app.layout = app.layout
    
    # Рендерим в HTML
    from dash import Dash
    import dash
    
    # Используем dash.render_template или просто сохраняем
    # Для простоты - используем встроенный метод
    
    print(f"Генерация dashboard..."  )
    
    # Создаём статический HTML
    import io
    from contextlib import redirect_stdout
    
    # Сохраняем через dash
    output_path = Path(output_html)
    
    # Для статического HTML нужно отрендерить
    # Используем простой подход - записываем HTML вручную
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Analytics Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; }}
        h3 {{ border-bottom: 2px solid #333; padding-bottom: 10px; margin-top: 30px; }}
        .metrics {{ display: flex; flex-wrap: wrap; }}
        .metric-card {{ 
            padding: 15px; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
            margin: 10px; 
            background: #fff;
            min-width: 200px;
        }}
        .metric-card h4 {{ margin: 0 0 10px 0; font-size: 14px; color: #666; }}
        .metric-card h3 {{ margin: 0; font-size: 24px; border: none; }}
        .metric-card small {{ color: #999; }}
        hr {{ margin-top: 40px; }}
        .footer {{ text-align: center; color: #999; }}
    </style>
</head>
<body>
    <h1>Analytics Dashboard</h1>
    
    <h3>Общая статистика</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Диалогов</h4><h3>{total_dialogs}</h3></div>
        <div class="metric-card"><h4>Пользователей</h4><h3>{total_users}</h3></div>
        <div class="metric-card"><h4>Период</h4><h3>{date_min[:10]} - {date_max[:10]}</h3></div>
    </div>
    
    <h3>Токены и стоимость</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Всего токенов</h4><h3>{total_tokens:,}</h3></div>
        <div class="metric-card"><h4>Среднее на диалог</h4><h3>{avg_tokens:,.0f}</h3></div>
        <div class="metric-card"><h4>Burned tokens</h4><h3>{total_burned:,}</h3><small>{burned_ratio:.2f}% от общих</small></div>
        <div class="metric-card"><h4>Стоимость ($)</h4><h3>${total_cost:.2f}</h3></div>
    </div>
    
    <h3>Качество агента</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Полезные сообщения</h4><h3>{useful_total}</h3></div>
        <div class="metric-card"><h4>Бесполезные сообщения</h4><h3>{useless_total}</h3></div>
        <div class="metric-card"><h4>Useful ratio</h4><h3>{useful_ratio:.1f}%</h3></div>
        <div class="metric-card"><h4>Диалоги с ошибками</h4><h3>{dialogs_with_burned}</h3><small>Среднее burned: {avg_burned_failed:.0f}</small></div>
    </div>
    
    <h3>Классификация</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Рабочие диалоги</h4><h3>{work_dialogs}</h3><small>{work_ratio:.1f}%</small></div>
        <div class="metric-card"><h4>Кандидаты на автоматизацию</h4><h3>{automation_candidates}</h3><small>{automation_ratio:.1f}%</small></div>
    </div>
    
    <h3>Сложность</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Simple</h4><h3>{complexity_dist.get('simple', 0)}</h3></div>
        <div class="metric-card"><h4>Medium</h4><h3>{complexity_dist.get('medium', 0)}</h3></div>
        <div class="metric-card"><h4>Complex</h4><h3>{complexity_dist.get('complex', 0)}</h3></div>
    </div>
    
    <h3>Периодичность</h3>
    <div class="metrics">
        <div class="metric-card"><h4>None</h4><h3>{periodicity_dist.get('none', 0)}</h3></div>
        <div class="metric-card"><h4>Daily</h4><h3>{periodicity_dist.get('daily', 0)}</h3></div>
        <div class="metric-card"><h4>Weekly</h4><h3>{periodicity_dist.get('weekly', 0)}</h3></div>
        <div class="metric-card"><h4>Monthly</h4><h3>{periodicity_dist.get('monthly', 0)}</h3></div>
    </div>
    
    <h3>Интеграции и инструменты</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Диалоги с интеграциями</h4><h3>{dialogs_with_int}</h3></div>
        <div class="metric-card"><h4>Уникальные интеграции</h4><h3>{len(unique_integrations)}</h3></div>
        <div class="metric-card"><h4>Уникальные инструменты</h4><h3>{len(unique_tools)}</h3></div>
        <div class="metric-card"><h4>Среднее tool calls</h4><h3>{avg_tool_calls:.1f}</h3></div>
    </div>
    
    <h3>Use Cases (кластеры)</h3>
    <div class="metrics">
        <div class="metric-card"><h4>В кластерах</h4><h3>{total_clusters}</h3></div>
        <div class="metric-card"><h4>Выбросы (outliers)</h4><h3>{outliers}</h3></div>
        <div class="metric-card"><h4>Средний размер кластера</h4><h3>{avg_cluster_size:.1f}</h3></div>
    </div>
    <div style="padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin: 10px;">
        <h4>Топ-5 кластеров</h4>
        <ul>
            {''.join(f'<li>Кластер {cid}: {count} диалогов</li>' for cid, count in top_5_clusters.items())}
        </ul>
    </div>
    
    <h3>Проблемы</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Провалы агента</h4><h3>{agent_failures}</h3></div>
        <div class="metric-card"><h4>Промпт-инъекции</h4><h3>{prompt_injections}</h3></div>
        <div class="metric-card"><h4>Чувствительные данные</h4><h3>{sensitive_data}</h3></div>
    </div>
    
    <h3>Языки</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Russian</h4><h3>{lang_dist.get('ru', 0)}</h3></div>
        <div class="metric-card"><h4>English</h4><h3>{lang_dist.get('en', 0)}</h3></div>
    </div>
    
    <h3>Уверенность классификации</h3>
    <div class="metrics">
        <div class="metric-card"><h4>Средняя confidence</h4><h3>{avg_confidence:.3f}</h3></div>
        <div class="metric-card"><h4>Низкая confidence (&lt;0.5)</h4><h3>{low_confidence}</h3></div>
    </div>
    
    <hr>
    <p class="footer">Generated from {analytics_csv.name}</p>
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
