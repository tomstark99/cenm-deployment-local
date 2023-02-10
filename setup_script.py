from ruamel.yaml import YAML

yaml = YAML()

with open(('cenm-auth/auth.conf'), 'r') as f:
    doc = yaml.load(f)

print(doc)