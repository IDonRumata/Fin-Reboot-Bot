import os

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        
        # Specific link replacements in CSV
        if filepath.endswith('content_blocks.csv'):
            replacements = {
                '🔗 Регистрация: https://bynex.io/trading/ru/?token=rt1257647&utm_source=reflink': '🔗 Регистрация: <a href="https://bynex.io/trading/ru/?token=rt1257647&utm_source=reflink">Bynex</a>',
                'Зарегистрируйтесь по ссылке: https://bynex.io/trading/ru/?token=rt1257647&utm_source=reflink': 'Зарегистрируйтесь на <a href="https://bynex.io/trading/ru/?token=rt1257647&utm_source=reflink">Bynex</a>',
                '🔗 Регистрация: https://whitebird.io/signup?refid=Un4pOq5CICr': '🔗 Регистрация: <a href="https://whitebird.io/signup?refid=Un4pOq5CICr">White Bird</a>',
                '🔗 Регистрация: https://www.bybit.com/invite?ref=RO35PR': '🔗 Регистрация: <a href="https://www.bybit.com/invite?ref=RO35PR">Bybit</a>',
                '🔗 Регистрация: https://freedom24.com/invite_from/16478129': '🔗 Регистрация: <a href="https://freedom24.com/invite_from/16478129">Freedom Finance Europe</a>',
                '🔗 Регистрация: https://freedombroker.kz/invite_from/17444475': '🔗 Регистрация: <a href="https://freedombroker.kz/invite_from/17444475">Freedom Finance Global</a>'
            }
            for old, new in replacements.items():
                if old in content:
                    content = content.replace(old, new)
                    modified = True

        # Replace dashes
        if '—' in content or '–' in content:
            content = content.replace('—', '-').replace('–', '-')
            modified = True
            
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {filepath}")
    except Exception as e:
        print(f"Error on {filepath}: {e}")

# Process CSV
fix_file('data/content_blocks.csv')

# Process Python files
for root, dirs, files in os.walk('bot'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

print('All replacements applied successfully.')
