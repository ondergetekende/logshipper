
class Context():
    __slots__ = ['pipeline_manager', 'variables', 'match', 'match_field',
                 'backreferences']

    def __init__(self, pipeline_manager):
        self.pipeline_manager = pipeline_manager
        self.variables = {}
        self.match = None
        self.match_field = None
        self.backreferences = []

    def interpolate_template(self, template):
        return template.format(*self.backreferences, **self.variables)

    def next_step(self):
        self.match = None
        self.match_field = None
        self.backreferences = []
