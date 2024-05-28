from django import forms

class Form(forms.Form):
    
    required_css_class = 'required'
    
    def __init__(self, *args, **kwargs):
        if 'label_suffix' not in kwargs:
            # We generally don't want automatic colons after field names
            kwargs['label_suffix'] = ''
        super(Form, self).__init__(*args, **kwargs)
        
    def _html_output(self, *args, **kwargs):
        for field in list(self.fields.values()):
            if field.help_text:
                field.widget.attrs['data-helptext'] = field.help_text
                field.help_text = None

        return super(Form, self)._html_output(*args, **kwargs)