# agent.md

## Про проєкт

Основна задача цього проєкту — **скрипти для Rhinoceros (RhinoScript / rhinoscriptsyntax на Python) та компоненти для Grasshopper**.
Це не застосунок і не бібліотека для збірки — це набір інструментів computational design, які запускаються всередині Rhino 6/7/8
(редактор `_ScriptEditor` / `_EditPythonScript`) або вставляються у GHPython-компоненти Grasshopper.

Прикладна область — розкрій та підготовка викрійок (зокрема шкіряні гаманці, патерни), робота з кривими, полілайнами,
bounding box, типами ліній та розбиттям кривих за кутом.

Сумісність коду: IronPython 2.7 і CPython 3 (Rhino 8). Багато скриптів мають українськомовні підказки в діалогах `rs.Get*`.

## Rhino Scripts

- Scripts run in Rhino's IronPython 2.7. Add `# -*- coding: utf-8 -*-` as the first line and avoid f-strings and Python 3-only syntax.
- Operate ONLY on the objects the user selected, never document-wide, unless explicitly told otherwise.
- Preserve the original layer, group membership and selection state of any object you modify or replace.
- Prefer click-based interaction (e.g., 'click near the end to trim') over abstract options like Start/End, because the user can't tell curve direction.
- Each new script needs: the script in its category subfolder, a toolbar button, and a README entry.
- Syntax-checking is not verification. At the end, state clearly which scripts were NOT run in Rhino and give a 3-step manual test for each.

## Директорії

- **`scripts/`** — Python-скрипти для Rhino (`rhinoscriptsyntax` / `Rhino.Geometry`), розкладені по підпапках = вкладках тулбара:
  - **`sizes/`** (вкладка «Розміри»): `BoundingBoxWithSize_Rhino8_CPlane.py` (ghosted bbox з підписами XYZ; `BoundingBoxWithSize.py` — стара версія), `BoundingBoxCenterLines.py`, `LabelClosedCurveSizes.py`, `draw_centered_rectangle.py` (прямокутник заданого розміру по центру CPlane).
  - **`curves/`** («Криві»): `SplitCrvByAngle.py`, `smooth_corners.py`, `GH_SplitCurveByAngle.py` (розбиття / заокруглення за кутом), `CrvToPolyline.py`, `TrimCrvEnds.py`, `KeepCrvEnds.py`, `TrimOutsidePanel.py`, `find_exact_connection.py` (точка контакту із фіксованою довжиною).
  - **`cut/`** («Різ»): `PreparePanelCut.py`, `SplitPanelsToMaterial.py` (панелі за лініями матеріалу: обрізка, шов 1 см, шматок відсувається на 50 мм, пари A–A, B–B…), `sel_curve_overlap.py` (дублікати / перекриття: виділені криві або всі).
  - **`analysis/`** («Аналіз»): аналіз панелі та різу — `SelectSmallClosedCurves.py`, `CheckTangentialCutRisks.py`, `RecommendCutTabs.py`, `AddCutTabs.py` (+ `.md` описи).
  - **`parts/`** («Parts», результат у шар `Parts::<Назва>`): `Panels.py` — панелі: копія замкненої кривої на місці в `Parts::Panels` (вхідна крива видаляється), номер `P<n>` (текст усередині за кліком + TextDot вище-зліва в підшарі `Parts::Panels::Dots`, UserText `Part`), вкладені криві — вирізи панелі; номер — найменший вільний (номер видаленої панелі повертається). `StripsFromCurves.py` — фаші (bordatura / rinforzo): кожна вибрана крива → прямокутник висотою H і довжиною кривої (+ запас); стовпчиком впритул у шар `Parts::Strips`, підписи `F<n>  L=… × H` + TextDot `F<n>` на кривій; нумерація продовжується з найбільшого `F<n>` у шарі. `Seam.py` — припуск на шов як окрема деталь: панель + клік біля ребра → як CopriZip (бере `CopriZip.flap`, імпорт усередині `main`, бо CopriZip імпортує з Seam), підпис `SA W`, група; шар `Parts::Seam`; опція `Points=Yes` бере `sewing_lengths` з `markup/sewing_points.py` — точки шва на копії ребра в `Parts::Seam`, у групі зі смугою (оригінал не чіпається). `CopriZip.py` — клапан над блискавкою: окрема деталь на ребрі панелі (кут–кут), офсет W назовні, кінці по продовженню сусідніх ребер; шар `Parts::CopriZip`, підпис `CZ W`. `JoinCorner.py` — дві деталі в куті (CopriZip / Seam, різні W) → одна: вибір деталей + клік біля кута, торці геть, зовнішні краї до перетину; пара торців — та, що дає найменше заповнення; шар/група першої, група другої зливається в неї. `ZipStops.py` — блискавки й каналіна: опція `Type` = `Zip` (обидві сторони, `Z<n>`, `Parts::Zip`) / `Can` (canalina / guida, одна сторона, `Can<n>`, `Parts::Canalina`); одна блискавка/каналіна = усі її лінії на всіх панелях (вибір по черзі); кожна лінія → свій шар, номер (UserText `Zip` + текст, опція `Style`), стопи на кінцях, група на лінію; сторона розбита (Zip 3+ ліній, Can 2+) → клік біля стику міняє стоп на риску; потім етап переносу номера на інший бік кривої. `ZipList.py` — таблиця для замовлення: блискавки — лінії одного номера → дві сторони з найближчими сумами, замовляється довша, вгору до 1 см, різниця > 5 мм або одна лінія — попередження, зведено «см × шт»; каналіна — повна довжина (сума ліній) окремою секцією; CSV `<файл>_zips.csv` поруч із `.3dm` + буфер обміну. `ReinfCircle.py` — кутове підсилення-коло: клік біля кута → сектор радіуса R між сторонами, на місці, підпис `RC<n>  R=…`, шар `Parts::Reinforcements` (інші форми — свої префікси RS, RT…). `LayoutParts.py` — розкладка для розкрою: копія кожної вибраної деталі (група цілком) в ряд від точки кліку (Enter — продовжити ряд), у підшар `<шар>::Layout`; оригінал лишається розміткою, UserText `LayoutOf` на копії.
  - **`markup/`** («Розмітка»): `PointsToCrosses.py` (точки / хмари / TextDot → хрестик або коло), `sewing_points.py`, `line_type.py` + `linetype.gh` (тип лінії `400,2`), `PatternTextStyles.py` (+ `_check.py`), `TextToDot.py`, `DotToPanelText.py`, `TextToCurves.py` (текст → криві для нестингу, перевернутий текст не дзеркалиться — як Draw forward на екрані), `Legend.py` (легенда підписів скриптів — лише наявні позначки, текст у точці кліку, Lang = UA / EN / IT).
  - `build_scripts_rui.py` — збирач тулбара `Scripts.rui` (6 вкладок: Розміри / Криві / Аналіз / Різ / Parts / Розмітка).
  - `tests/` — перевірки (частина запускається в Rhino 8 через `rhinocode`).
  - Імпорт між папками — через `sys.path` від `__file__` (напр. `cut/SplitPanelsToMaterial.py` бере `markup/PatternTextStyles.py`).

- **`Grasshoper scripts/`** — визначення Grasshopper (`.gh`): `bounding_dimensions.gh`, `Len_dimentions.gh`,
  `polyline.gh`, `drag.gh`, `sew points.gh`, `divanno_v1.gh`.

- **`Patterns/`** — вихідні викрійки та матеріали для розкрою (`.3dm`, `.dxf`, `.pdf`): гаманці, тоут, origami-шаблони.

- Кореневий `allalunga.3dm` — робочий файл Rhino.

## Робота з кодом

- Нові скрипти класти в підпапку `scripts/<вкладка>/` (sizes / curves / analysis / cut / parts / markup) або `Grasshoper scripts/` (`.gh`); у `GROUPS` — `py("<папка>/<Script>.py")`.
- Тримати сумісність з IronPython 2.7 та CPython 3, якщо явно не сказано інше.
- Одиниці та допуски брати з документа (`sc.doc.ModelAbsoluteTolerance`), не хардкодити.
- Скрипти, що **створюють частини** (фаші, підсилення тощо), лежать у `scripts/parts/`, кладуть результат у шар `Parts::<Назва>` і йдуть у вкладку тулбара **Parts** (`py("parts/<Script>.py")`).

## Тулбар (`Scripts.rui`)

- Новий скрипт → дописати рядок у `GROUPS` у `scripts/build_scripts_rui.py` (і в таблицю в `README.md`).
- **Збирач `build_scripts_rui.py` НЕ запускати** — користувач перезбирає `Scripts.rui` сам (при закритому Rhino). Наприкінці відповіді нагадати команду збірки.
- Після кожного створеного / зміненого скрипта відповідь закінчувати повним макросом для кнопки:
  `!_-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/<підпапка/><Script>.py"`

## Git

- Репозиторій: https://github.com/Miity/rhino_scripts_panneling (публічний, гілка `main`).
- Після кожної завершеної зміни — коміт і пуш: `git add -A && git commit -m "<що змінено>" && git push`.
- `Patterns/` і `*.3dm` у `.gitignore` (сторонні викрійки / робочі файли) — не додавати в репозиторій.
