import os
from importlib import import_module

model_files = [f for f in os.listdir(os.path.dirname(__file__)) if f.endswith('.py') and f != '__init__.py']

for file in model_files:
    module_name = file[:-3]
    import_module(f'.{module_name}', package=__name__)
