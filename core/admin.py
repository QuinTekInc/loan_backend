from django.contrib import admin
from django.apps import apps

# Register your models here.
models_to_register = apps.get_app_config('core').models.items()

for  model_name, model in models_to_register:
    
    if not admin.site.is_registered(model):
        admin.site.register(model)
        pass

    pass
