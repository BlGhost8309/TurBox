import os

files = [f for f in os.listdir('.') if f.endswith('.py') and os.path.isfile(f)]

with open('scriptsNames.txt', 'w', encoding='utf-8') as f:
    f.write(', '.join(files))
