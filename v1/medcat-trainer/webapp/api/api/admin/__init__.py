from .models import *
from .actions import *
from ..models import *

admin.site.register(Entity)
admin.site.register(MetaTaskValue)
admin.site.register(MetaTask)
admin.site.register(Vocabulary)
admin.site.register(Relation)
admin.site.register(EntityRelation)
admin.site.register(ProjectGroup, ProjectGroupAdmin)
admin.site.register(ProjectAnnotateEntities, ProjectAnnotateEntitiesAdmin)
admin.site.register(AnnotatedEntity, AnnotatedEntityAdmin)
admin.site.register(MetaAnnotation, MetaAnnotationAdmin)
admin.site.register(ConceptDB, ConceptDBAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(ExportedProject, ExportedProjectAdmin)
admin.site.register(ProjectMetrics, ProjectMetricsAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(ModelPack, ModelPackAdmin)
admin.site.register(MetaCATModel, MetaCATModelAdmin)
