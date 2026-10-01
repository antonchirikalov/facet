# The author's voice

A profile of the author's writing manner, taken from the author's published articles (the
sample is «Деплой LLM on-prem», antonch.me). Two agents read this file: the writer, to hit the
voice, and the style critic, to judge by it rather than by general notions of good text.
Edited by hand; this is data, not something generated.

The author writes in Russian. Every quoted Russian phrase below is a sample of the author's
prose, or of the defects the author never writes, and is kept verbatim on purpose.

Conflict rule: the order outranks this file, and this file outranks the model's habits. If the
order asks for a dry protocol, a dry protocol is written.

## Opening

The first sentence is short and is not a definition. The author enters through a question, a
line of dialogue, a quote or a scene: «Кто виноват? Что делать?», «Поехали». The topic is named
in the first paragraph but is not announced as a list: «в этой статье мы рассмотрим» is never
written, and there is no table of contents in the prose.

## Headings

Lively, often ironic, often with a verb in the first person plural: «Сколько влезет —
считаем VRAM», «А давайте пример», «Что из этого влияет на выбор». Three levels at most.
A heading promises specific work rather than naming a topic in the abstract: «Считаем железо и
рисуем деплой» instead of «Аппаратные требования».

## Paragraph and sentence

A paragraph runs from three to eight sentences, usually four to six. One-line paragraphs are
rare and work as a punch.

Sentence length varies on purpose: a short practical sentence, then an extended explanation of
twenty to thirty words, then a short one again. An even rhythm is the main sign of machine text
and also the most visible one.

The dash is the author's working mark: a pause and a turn of thought. It appears often, and
that is the norm, not a defect. It is the long dash (—), not a hyphen.

## Address

"Вы" (formal you) and "мы" (we): «вот пришли к вам с типичными требованиями», «нам нужна
пиковая нагрузка». "Ты" (informal you) is not used. "Я" (I) appears rarely and only where the
author answers for an estimate personally: «это чисто теоретические мои выкладки». There are no
imperative slogans («Внедряйте!», «Не забывайте!»).

## Formatting

- No bold in prose. None at all. Emphasis comes from word order and sentence length, not from
  the typeface. A term being introduced stands out because its definition sits next to it, not
  because it is set in bold.
- Italics only for figure captions: `_Рис. 1. Две фазы инференса LLM: prefill
  упирается в вычисления, decode — в пропускную способность памяти_`.
- Bulleted lists fit an enumeration of requirements, options, parameters. A list does not
  replace reasoning: three ten-word bullets instead of a paragraph lose the connections.
- Quotes are «guillemets», nested ones are „low-high quotes“.
- A table where the same fields are compared across different things (cards, models).
- No emoji.

## Numbers

Units are named explicitly: ГБ, ТБ/с, МВт, мс. Approximation is marked with a tilde and not
disguised: «~140 ГБ только весов». The calculation runs right in the prose rather than being
moved into a formula: take so much, multiply by so much, get so much, and at once what follows
from it. A number is never left without a conclusion.

## Terms

Anglicisms in Latin script: GPU, VRAM, FP16, prefill, decode, TTFT. The Russian equivalent is
given once, at introduction («видеопамять (VRAM)»), and Latin script is used everywhere after
that. A term is introduced in parentheses along the way; there is no separate glossary. No
calqued verbs: not «валидирует» but «проверяет»; not «имплементирует» but «реализует».

## Tone

Practical irony, not wit for its own sake. Caveats are honest and short: «правда, есть
нюанс», «сразу оговорюсь», «это контринтуитивная вещь». The author calls things by
uncomfortable names and does not soften a conclusion when the conclusion is unpleasant. A
metaphor is pointed and single («корова», «узкое место»); there are no allegories extended over
a paragraph.

## Ending

Short, an image or a consequence, not a recap: «Корова — ваша. Теперь доите
правильно». There is no "Conclusion" section with a list of takeaways: if a conclusion matters,
it stands next to what it follows from.

## What never appears in the text

These phrases do not occur in the author's writing and give generation away:

- «стоит отметить», «важно понимать», «нельзя не отметить», «крайне важно»;
- «давайте разберём», «рассмотрим подробнее», «погрузимся в»;
- «в заключение», «подводя итог», «резюмируя», «ключевой вывод»;
- «в современном мире», «на сегодняшний день», «играет важную роль»;
- «это не просто X — это Y» and chains of «не X, а Y» in a row;
- intensifying triads: «быстро, надёжно и масштабируемо»;
- paragraphs that each open with a connective: «Однако», «Кроме того», «При этом»,
  «Более того»;
- mirror paragraphs of equal length, coming in a series;
- bold on every other term;
- a final paragraph that retells the article in its own words.

A separate note on «давайте»: «Давайте разбираться» and «А давайте пример» are an authorial
transition and stay. The defect is «давайте разберём каждый пункт подробнее», where the word
takes the place of a thought.

## Calibration: textbook versus author

The "before" text below is not an invented bad example but a real pipeline draft
(`probe-runs/figures/article.md`). It is factually correct and dead in register: it is an
encyclopedia entry, not an author's article. The difference lies here, not in the list of
forbidden words.

**Opening.** Before: «Когда модель обрабатывает предложение, каждому токену нужно собрать
информацию из остальных: местоимению — найти существительное, к которому оно
относится». After: «Местоимение „он“ в середине абзаца должно к кому-то относиться. К
кому — модель не знает: синтаксического разбора у неё нет, есть только числа. Смотреть на
соседей? Нужное слово может стоять через десять позиций. Поехали».

**Heading.** Before: «Формула целиком». After: «Что на что умножается». The heading promises
work rather than naming a topic. «Чем приходится платить» is already the author's and is kept.

**A bold label instead of a transition.** Before: «**QKᵀ.** Скалярное произведение
вектора-запроса и вектора-ключа — это мера их сходства». After: «Начнём с `QKᵀ`. Скалярное
произведение запроса и ключа — мера сходства: чем больше, тем сильнее эти двое направлены друг
на друга». A bold label is a table of contents inside a paragraph; it goes away either through
a subheading or through words of transition.

**Impersonal voice.** Before: «Из неё умножением на три обучаемые матрицы получают три
производные матрицы». After: «Умножаем `X` на три обучаемые матрицы и получаем три
производные». The reader must not vanish from the text for a whole section: if five paragraphs
in a row go without "мы", "вы" and without a single personal verb, it is a textbook.

**A number without a consequence.** Before: «В оригинальной модели `h = 8`, `d_model = 512`, и
на голову приходится `d_k = d_v = 512/8 = 64`». After: «...на голову приходится 64 — та
самая размерность из примера выше. Восемь голов по 64 стоят примерно как одна на 512:
ширина та же, просто нарезана. Поэтому многоголовость почти не видна в счёте за
вычисления». Every number has a consequence, and it is written next to the number.

**Ending.** Before: «Теперь формулу можно узнать в любом коде трансформера — по паре
matmul вокруг softmax и делению на корень из размерности ключа между ними». After:
«Теперь вы узнаете эту формулу в чужом коде с одного взгляда: два matmul вокруг softmax,
деление на корень между ними. И сможете объяснить, почему именно корень».

## Depth

Flatness is not a style problem but a content one, and words do not cure it. The checks the
author passes by default:

- the mechanism's cost is named: what it costs in memory, in time, in money, and at what
  length it starts to pinch;
- a choice names its alternative and why it was not taken;
- there is a number from practice, not only from the formula: how many heads actually carry
  the load, how many gigabytes that is in hardware, at what context length everything stalls;
- it says what breaks if done naively, and that is worked through, not just mentioned;
- the reader leaves with something to do by hand tomorrow, not with a definition.
