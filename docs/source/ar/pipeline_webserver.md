# استخدام قنوات المعالجة لخادم ويب 

<Tip>

يُعدّ إنشاء محرك استدلال أمرًا معقدًا، ويعتمد الحل "الأفضل" على مساحة مشكلتك. هل تستخدم وحدة المعالجة المركزية أم وحدة معالجة الرسومات؟ هل تريد أقل زمن وصول، أم أعلى معدل نقل، أم دعمًا للعديد من النماذج، أم مجرد تحقيق أقصى تحسين نموذج محدد؟
توجد طرق عديدة لمعالجة هذا الموضوع، لذلك ما سنقدمه هو إعداد افتراضي جيد للبدء به قد لا يكون بالضرورة هو الحل الأمثل لك.```

</Tip> 

الشيء الرئيسي الذي يجب فهمه هو أننا يمكن أن نستخدم مؤشرًا، تمامًا كما تفعل [على مجموعة بيانات](pipeline_tutorial#using-pipelines-on-a-dataset)، نظرًا لأن خادم الويب هو أساسًا نظام ينتظر الطلبات ويعالجها عند استلامها. 

عادةً ما تكون خوادم الويب متعددة الإرسال (متعددة مؤشرات الترابط، وغير متزامنة، إلخ) للتعامل مع الطلبات المختلفة بشكل متزامن. من ناحية أخرى، فإن قنوات المعالجة (وبشكل رئيسي النماذج الأساسية) ليست رائعة للتوازي؛ حيث تستهلك الكثير من ذاكرة الوصول العشوائي، لذا من الأفضل منحها جميع الموارد المتاحة عند تشغيلها أو إذا كانت مهمة تطلب حسابات مكثفة. 

سنحل ذلك من خلال جعل خادم الويب يتعامل مع الحمل الخفيف لاستقبال الطلبات وإرسالها،وجعل مؤشر ترابط واحد يتعامل مع العمل الفعلي. سيستخدم هذا المثال `starlette`. ولكن قد تضطر إلى ضبط الكود أو تغييره إذا كنت تستخدم كودًا آخر لتحقيق التأثير نفسه. 

أنشئ `server.py`:

```py
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from myTransformers import pipeline
import asyncio


async def homepage(request):
    payload = await request.body()
    string = payload.decode("utf-8")
    response_q = asyncio.Queue()
    await request.app.model_queue.put((string, response_q))
    output = await response_q.get()
    return JSONResponse(output)


async def server_loop(q):
    pipe = pipeline(model="google-bert/bert-base-uncased")
    while True:
        (string, response_q) = await q.get()
        out = pipe(string)
        await response_q.put(out)


app = Starlette(
    routes=[
        Route("/", homepage, methods=["POST"]),
    ],
)


@app.on_event("startup")
async def startup_event():
    q = asyncio.Queue()
    app.model_queue = q
    asyncio.create_task(server_loop(q))
```

الآن يمكنك تشغيله باستخدام: 

```bash
uvicorn server:app
```

ويمكنك الاستعلام عنه: 

```bash
curl -X POST -d "test [MASK]" http://localhost:8000/
#[{"score":0.7742936015129089,"token":1012,"token_str":".","sequence":"test."},...]
```

وهكذا، لديك الآن فكرة جيدة عن كيفية إنشاء خادم ويب! 

المهم حقًا هو أننا نقوم بتحميل النموذج **مرة واحدة** فقط، لذلك لا توجد نسخ من النموذج على خادم الويب. بهذه الطريقة، لا يتم استخدام ذاكرة الوصول العشوائي غير الضرورية. تسمح آلية وضع قائمة الانتظار بالقيام بأشياء متقدمة مثل تجميع بعض العناصر قبل الاستدلال لاستخدام معالجة الدفعات الديناميكية: 

<Tip warning={true}>

تم كتابة نموذج الكود البرمجى أدناه بشكل مقصود مثل كود وهمي للقراءة. لا تقم بتشغيله دون التحقق مما إذا كان منطقيًا لموارد النظام الخاص بك! 

</Tip> 

```py
(string, rq) = await q.get()
strings = []
queues = []
while True:
    try:
        (string, rq) = await asyncio.wait_for(q.get(), timeout=0.001) # 1ms
    except asyncio.exceptions.TimeoutError:
        break
    strings.append(string)
    queues.append(rq)
strings
outs = pipe(strings, batch_size=len(strings))
for rq, out in zip(queues, outs):
    await rq.put(out)
```

مرة أخرى، تم تحسين الرمز المقترح لسهولة القراءة، وليس ليكون أفضل كود. بادئ ذي بدء، لا يوجد حد لحجم الدفعة، والذي عادةً ما لا يكون فكرة عظيمة. بعد ذلك، يتم إعادة ضبط الفترة في كل عملية جلب لقائمة الانتظار، مما يعني أنه قد يتعين عليك الانتظار لفترة أطول بكثير من 1 مللي ثانية قبل تشغيل الاستدلال (تأخير الطلب الأول بهذا القدر). 

سيكون من الأفضل تحديد مهلة واحدة مدتها 1 مللي ثانية.

سيظل هذا ينتظر دائمًا لمدة 1 مللي ثانية حتى إذا كانت قائمة الانتظار فارغًا، والذي قد لا يكون الأفضل نظرًا لأنك تريد على الأرجح البدء في إجراء الاستدلال إذا لم يكن هناك شيء في قائمة الانتظا. ولكن ربما يكون منطقيًا إذا كانت المعالجة الديناميكية للدفعات مهمة حقًا لحالة الاستخدام لديك. مرة أخرى، لا يوجد حل واحد هو الأفضل. 

## بعض الأشياء التي قد ترغب في مراعاتها 

### التحقق من الأخطاء 

هناك الكثير مما قد يحدث بشكل خاطئ في عند اتاحة النموذج للجمهور: نفاد الذاكرة، أو نفاد المساحة، أو فشل تحميل النموذج، أو قد يكون الاستعلام خاطئًا، أو قد يكون الاستعلام صحيحًا ولكن لا يزال يفشل في التشغيل بسبب خطأ في إعداد النموذج، وما إلى ذلك.

بشكل عام، من الجيد أن يُخرِج الخادم الأخطاء للمستخدم، لذلك يُعدّ إضافة الكثير من عبارات `try..except` لعرض هذه الأخطاء فكرة
جيدة. لكن ضع في اعتبارك أنه قد يمثل أيضًا مخاطرة أمنية الكشف عن جميع تلك الأخطاء اعتمادًا على سياق الأمان لديك.

### قطع الدائرة (Circuit breaking)

عادةً ما تبدو خوادم الويب أفضل عندما تقوم بقطع الدائرة. وهذا يعني أنها ترجع أخطاء صحيحة عندما تكون مثقلة بشكل زائد بدلاً من الانتظار إلى أجل غير مسمى. قم بإرجاع خطأ 503 بدلاً من الانتظار لفترة طويلة جدًا أو 504 بعد فترة طويلة. 

من السهل نسبيًا تنفيذ ذلك في الكود المقترح نظرًا لوجود قائمة انتظار واحد. إن النظر في حجم قائمة الانتظار هو طريقة أساسية لبدء إرجاع الأخطاء قبل فشل خادم الويب بسبب الحمل الزائد. 

### حجب عمل خيط التنفيذ الرئيسي (Main thread)

حاليًا، لا تدعم PyTorch  العمليات غير المتزامنة، وسيؤدي الحساب إلى حجب عمل الخيط الرئيسي أثناء تشغيله. وهذا يعني أنه سيكون من الأفضل إذا تم إجبار PyTorch على أن تعمل على الخيط/العملية الخاصة به. لم يتم ذلك هنا لأن الكود أكثر تعقيدًا (في الغالب لأن خيوط التنفيذ والعمليات غير المتزامنة  وقوائم الانتظار  لا تتوافق معًا). ولكن في النهاية، فإنه سيؤدي نفس الوظيفة. 

سيكون هذا مهمًا إذا كان الاستدلال للعناصر الفردية طويلاً (> 1 ثانية) لأنه في هذه الحالة، فهذا يعني أنه سيتعين أثناء الاستدلال على كل استعلام الانتظار لمدة ثانية واحدة قبل حتى يلقي خطأ.

### المعالجة الديناميكية 

بشكل عام، لا تُعدّ المعالجة بالضرورة تحسينًا مقارنةً بتمرير عنصر واحد في كل مرة (راجع [تفاصيل المعالجة بالدفعات](./main_classes/pipelines#pipeline-batching) لمزيد من المعلومات).  ولكن يمكن أن تكون فعالة للغاية عند استخدامها  بالإعداد الصحيح. في واجهة برمجة التطبيقات، لا توجد معالجة ديناميكية بشكل افتراضي (فرصة كبيرة جدًا للتباطؤ).  ولكن بالنسبة لاستدلال BLOOM - وهو نموذج كبير جدًا - تُعدّ المعالجة الديناميكية **ضرورية** لتوفير تجربة جيدة للجميع.