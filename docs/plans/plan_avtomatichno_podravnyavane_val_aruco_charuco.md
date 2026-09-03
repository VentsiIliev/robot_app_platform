# План за автоматично локализиране и подравняване на вертикалния вал чрез ArUco/ChArUco

## 1. Цел

Целта е да се премахне необходимостта операторът всеки път ръчно да подравнява робота спрямо вертикалния вал, върху който се изпълнява paint trajectory.

Системата трябва да позволява:

- еднократно прецизно ръчно подравняване;
- запазване на това подравняване като референтно;
- автоматично локализиране на вала чрез ArUco маркер;
- интерактивно насочване на оператора при грубо разместване;
- автоматична фина корекция чрез малки итеративни движения на робота;
- автоматична проверка преди всяка paint trajectory;
- блокиране на боядисването при невалидна позиция или ориентация;
- бъдещо добавяне на автоматична компенсация по RZ.

---

## 2. Основна идея

На върха на вертикалния вал се поставя ArUco маркер.

Маркерът не определя сам по себе си точката за боядисване. Той служи само като стабилна и лесно откриваема визуална референция за позицията на вала.

### 2.1. Координатни системи и трансформационен contract

Всички offset-и трябва да имат изрично зададени source и target frame. В документа се използва нотацията:

```text
T_A_B = позата на frame B, изразена във frame A
```

За камера върху робота основната верига е:

```text
T_base_camera(q)       = текуща camera pose от robot pose + hand-eye calibration
T_camera_marker        = marker pose от ArUco детекцията
T_base_marker          = T_base_camera(q) * T_camera_marker

T_marker_paint_ref     = референтната трансформация, записана при калибрация
T_base_paint_ref       = T_base_marker * T_marker_paint_ref
```

`q` означава robot pose/joint state, синхронизиран с timestamp-а на camera frame-а. Посоката и знакът на показваните X/Y корекции се извеждат от тези трансформации и се проверяват с known-displacement тест; не се определят само от pixel difference.

При първоначална калибрация:

1. Роботът и валът се подравняват ръчно възможно най-точно.
2. Камерата открива ArUco маркера.
3. Изчислява се `T_marker_paint_ref` между маркера и желаната paint reference позиция.
4. Трансформацията и provenance информацията на използваните калибрации се записват като референция.

След това при нормална работа:

```text
T_base_marker_current = T_base_camera(q) * T_camera_marker
T_base_paint_ref      = T_base_marker_current * T_marker_paint_ref

error_xy = XY разликата между текущия и необходимия paint reference frame
```

Целта е:

```text
error -> 0
```

---

## 3. Роля на ChArUco калибрацията

ChArUco board може да се използва за определяне/проверка на координатната система на paint платформата. Това е отделна задача от camera intrinsic calibration.

Необходими prerequisites:

- валидни camera intrinsics и distortion coefficients;
- валидна hand-eye/camera-to-robot трансформация;
- известна и versioned геометрия на ChArUco board-а;
- board, монтиран постоянно или в механично доказано повторяема позиция.

Тя може да замени текущата ръчна work-object калибрация, ако е монтирана:

- постоянно;
- или в механично повторяема позиция.

Препоръчителна трансформационна верига:

```text
T_base_camera * T_camera_charuco = T_base_paint_platform

robot_base
   |
   +-- paint_platform_wobj        <- ChArUco + intrinsics + hand-eye
           |
           +-- shaft_reference    <- локализиране чрез ArUco
                   |
                   +-- paint trajectory
```

ChArUco локализацията се използва за:

- X/Y/Z ориентация на платформата;
- RX/RY/RZ на платформата;
- стабилна референтна координатна система.

ChArUco сама по себе си не заменя work-object калибрацията. Замяната е допустима само след измерване на точността на цялата верига `base -> camera -> board` и сравнение с process tolerance-а.

ArUco на вала се използва за:

- X позиция на вала;
- Y позиция на вала;
- по-късно RZ на вала.

---

## 4. Версия 1 — само XY

Първата версия трябва да е максимално проста.

Използвани степени на свобода:

```text
X  = автоматично
Y  = автоматично
Z  = фиксирано
RX = фиксирано
RY = фиксирано
RZ = фиксирано / само за проверка
```

Преди добавяне на RZ компенсация трябва да се потвърди, че XY точността и повторяемостта са достатъчни за paint процеса.

---

## 5. Референтна калибрация

### 5.1. Ръчно подравняване

Операторът:

1. поставя вала;
2. позиционира робота в желаната paint reference позиция;
3. проверява физически подравняването;
4. стартира процедура `Calibrate Shaft Reference`.

### 5.2. Измерване

Системата:

1. открива ArUco маркера;
2. събира няколко последователни стабилни измервания;
3. изчислява `T_base_marker` от синхронизираните camera и robot данни;
4. изчислява и записва `T_marker_paint_ref`.

За диагностика от трансформацията могат да се покажат derived XY стойности:

```text
marker_to_paint_ref_x = +42.36 mm
marker_to_paint_ref_y = -18.21 mm
```

Добре е едновременно да се запише и роботната поза:

```yaml
shaft_reference:
  t_marker_paint_ref: [... 4x4 homogeneous transform ...]

  robot_pose:
    x_mm: ...
    y_mm: ...
    z_mm: ...
    rx_deg: ...
    ry_deg: ...
    rz_deg: ...

  marker_id: ...
  calibration_timestamp: ...
  calibration_fingerprints: ...
```

---

## 6. Проверка на текущото подравняване

При текуща детекция се пресмята:

```text
T_base_marker_current = T_base_camera(q) * T_camera_marker
T_base_paint_ref      = T_base_marker_current * T_marker_paint_ref
```

XY грешката се изразява в избрания authoritative platform/paint frame:

```text
error_x = required_paint_ref_x - current_paint_ref_x
error_y = required_paint_ref_y - current_paint_ref_y
```

Общата XY грешка:

```text
error_xy = sqrt(error_x^2 + error_y^2)
```

Посоката на корекция:

```text
direction = atan2(error_y, error_x)
```

---

## 7. Интерактивен режим за оператора

В Operator Dashboard да има бутон:

```text
[ Align Shaft ]
```

При стартиране:

- показва live camera frame;
- открива ArUco маркера непрекъснато;
- показва текущия XY error;
- показва стрелка за необходимата посока;
- показва величината на корекцията;
- по-късно показва и RZ корекция.

Примерен интерфейс:

```text
Marker detected:  YES

X correction:   +3.2 mm
Y correction:   -1.8 mm

Total error:     3.67 mm

        ↘
    MOVE SHAFT

RZ: ignored for now
```

Когато позицията е в допустимия tolerance:

```text
✓ SHAFT ALIGNED

X error: +0.18 mm
Y error: -0.12 mm
XY error: 0.22 mm

[ Finish ]
```

---

## 8. Филтриране на ArUco измерванията

Не трябва да се използва директно едно измерване от един кадър.

Всеки measurement sample трябва да съдържа:

```text
camera_frame_timestamp
robot_pose_timestamp
robot_pose / joint state
marker_pose
marker_id
reprojection_error
corner/detection quality
```

Кадри от различни robot poses не се смесват в една стабилна серия. Sample се отхвърля при frame timeout, прекалено голяма времева разлика между frame и robot pose или недостатъчно detection quality.

### 8.1. Live display

За визуализация може да се използва:

- rolling average;
- exponential low-pass filter;
- median от последните N кадъра.

Пример:

```text
filtered_x = 0.8 * previous_x + 0.2 * detected_x
filtered_y = 0.8 * previous_y + 0.2 * detected_y
```

### 8.2. Крайна валидация

За крайно решение се изискват няколко стабилни кадъра. Предпочитат се median и robust spread (например MAD), за да не може единичен outlier да премести резултата.

Пример:

```text
required_stable_frames = 10
max_position_spread_mm = 0.2
```

---

## 9. Hysteresis и стабилно състояние ALIGNED

За да не превключва състоянието постоянно:

```text
ALIGNED
NOT ALIGNED
ALIGNED
NOT ALIGNED
```

трябва да има hysteresis.

Пример:

```text
enter_aligned_threshold = 0.5 mm
leave_aligned_threshold = 0.8 mm
```

За `ALIGNED`:

```text
error_xy < 0.5 mm
за N последователни кадъра
```

За излизане от `ALIGNED`:

```text
error_xy > 0.8 mm
```

---

## 10. Създаване и замяна на референция

Операциите трябва да са разделени:

```text
[ Create Initial Reference ]   <- само когато няма референция
[ Replace Reference ]          <- когато вече има референция
```

И двете са защитени maintenance/admin операции с confirmation, operator identity и audit log.

Примерен coarse threshold:

```text
reference_capture_limit = 5.0 mm
```

`Create Initial Reference` се разрешава само ако:

- ArUco marker е открит;
- marker ID е правилният;
- measurement е стабилен;
- camera/robot pose и всички calibration prerequisites са валидни;
- RZ е в разрешен диапазон, когато RZ бъде добавено.

`Replace Reference` допълнително изисква:

- сравнение old/new с ясно показан delta;
- текущата позиция да е в `reference_capture_limit` спрямо старата референция;
- изрично потвърждение от упълномощен потребител.

След натискане:

```text
T_marker_paint_ref = current calibrated marker-to-paint relationship
```

Това позволява след механична настройка или сервиз операторът лесно да създаде нова валидна референция.

Важно:

`5 mm` е threshold за разрешаване на рекалибрация, а не tolerance за боядисване.

---

## 11. Quick Verify преди всяка Paint Trajectory

Преди изпълнение на paint trajectory трябва автоматично да се изпълнява кратка проверка от определена observation pose.

Проверката е paint-specific правило и трябва да бъде част от paint execution state machine, а не само от UI и не от общия `MotionService`. Тъй като изчаква движение и camera frames, тя не трябва да се изпълнява в `BaseProcess._on_start()`.

Процедура:

```text
Paint requested
      |
      v
Move to shaft_verification_pose
      |
      v
Wait for robot/camera settle
      |
      v
Discard frames older than pose arrival
      |
      v
Detect shaft marker
      |
      v
Collect stable samples
      |
      v
Calculate XY error
      |
      v
Validate thresholds
      |
  +---+---+
  |       |
 PASS    FAIL
  |       |
Paint    Block
```

Пример:

```text
marker detected       = required
stable measurements   = required
samples are fresh     = required
robot pose synchronized = required
XY error <= 0.5 mm    = required
RZ within bounds      = required later
```

Verification result съдържа `verified_at`, `frame_timestamp`, `robot_pose_timestamp` и `expires_at`. Paint може да започне само преди `expires_at`; всяко движение, calibration change или ново несъответствие инвалидира резултата. Не трябва да се използва последният наличен кадър без доказателство, че е заснет след достигане на verification pose.

При fail:

```text
PAINT BLOCKED

Shaft position has changed.

X correction: -2.8 mm
Y correction: +1.4 mm
Total error:   3.13 mm

[ Align Shaft ]
[ Retry ]
```

---

## 12. Състояния

Състоянието не е една линейна enum стойност. То се моделира като независими компоненти:

```text
reference_state:    MISSING | VALID | STALE
detection_state:    NOT_DETECTED | UNSTABLE | STABLE
alignment_state:    UNKNOWN | OUT_OF_TOLERANCE | ALIGNED
verification_state: NOT_VERIFIED | VERIFIED | EXPIRED
operation_state:    IDLE | ALIGNING | VERIFYING | FAILED
```

`ready_to_paint` е производна стойност:

```text
ready_to_paint =
    reference_state == VALID
    and detection_state == STABLE
    and alignment_state == ALIGNED
    and verification_state == VERIFIED
```

`VERIFIED` трябва да се инвалидира при:

- промяна на shaft reference;
- промяна на camera calibration;
- промяна на work object;
- изгубен marker;
- установено движение на вала;
- промяна на relevant tool/camera transform;
- рестартиране, ако няма гаранция, че геометрията е запазена.

---

## 13. RZ — следващ етап

След като XY точността бъде потвърдена, да се добави RZ.

Първата стъпка не е задължително автоматична компенсация.

Първо RZ може да се използва само като boundary check.

Пример:

```text
reference_rz = RZ при референтната калибрация

error_rz = shortest_angle(reference_rz - current_rz)
```

Примерни граници:

```text
|RZ error| <= 2 deg       -> OK
2-5 deg                   -> warning
> 5 deg                   -> paint blocked
```

Точните стойности трябва да се определят експериментално.

UI:

```text
RZ error: +3.4°

ROTATE SHAFT CCW 3.4°
```

---

## 14. Ротация на референтния XY offset

След добавяне на RZ, XY offset не трябва просто да се използва като фиксиран `[dx, dy]` в глобалната координатна система.

Запазва се offset в marker/shaft reference frame:

```text
offset_ref = [dx, dy]
```

При промяна на RZ:

```text
delta_rz = current_rz - reference_rz
```

Offset се завърта:

```text
dx_rot =
    cos(delta_rz) * dx
    - sin(delta_rz) * dy

dy_rot =
    sin(delta_rz) * dx
    + cos(delta_rz) * dy
```

По-добрият краен вариант е да се използва трансформация:

```text
T_marker_to_paint_reference
```

и:

```text
T_platform_to_paint =
    T_platform_to_marker
    *
    T_marker_to_paint_reference
```

---

## 15. Автоматична фина XY корекция

След като операторът е поставил вала достатъчно близо и RZ е в безопасни граници, системата може да направи автоматична fine alignment процедура.

Автоматичната корекция движи робота, не физически вала. Затова преди имплементация трябва да бъде избран и тестван един authoritative contract:

1. `T_base_paint_ref` се обновява и цялата paint trajectory се трансформира към новия runtime paint frame; или
2. trajectory е относителна спрямо коригираната reference pose и изпълнителят гарантира, че корекцията се запазва.

Не е допустимо роботът да бъде преместен до коригирана pose, а след това да се изпълни стара абсолютна trajectory, която губи корекцията. V1 използва само operator guidance и verification; automatic motion се активира едва след като този contract е реализиран и тестван end-to-end.

Това представлява ограничен visual-servo loop.

```text
Detect
   |
Calculate error
   |
Small robot correction
   |
Detect again
   |
Repeat
```

Не трябва да се прави директно движение с цялата измерена грешка.

Използва се gain:

```text
correction_x = K * error_x
correction_y = K * error_y
```

Пример:

```text
K = 0.5
```

Ако:

```text
error_x = +4.0 mm
error_y = -2.0 mm
```

първата корекция е:

```text
dx = +2.0 mm
dy = -1.0 mm
```

След това се прави нова детекция.

---

## 16. Ограничения на автоматичната fine alignment процедура

Автоматичният loop трябва да работи само в малка, предварително валидирана област.

Примерни начални стойности:

```text
max_initial_xy_error     = 5.0 mm
max_allowed_rz_error     = 3.0 deg

gain                     = 0.5

max_step_per_iteration   = 1.0 mm
fine_step_limit          = 0.2 mm

alignment_tolerance      = 0.3 mm

max_iterations           = 10
```

Тези стойности са само начални и трябва да се настроят експериментално.

---

## 17. Adaptive step size

Стъпката може да намалява при приближаване към целта.

Пример:

```text
error > 2.0 mm:
    max_step = 1.0 mm

0.5 mm < error <= 2.0 mm:
    max_step = 0.5 mm

error <= 0.5 mm:
    max_step = 0.1-0.2 mm
```

Това позволява:

- по-бързо първоначално сближаване;
- малки и точни движения близо до target-а.

---

## 18. Условия за прекратяване на автоматичната корекция

Automatic fine alignment трябва незабавно да се прекрати при:

- marker lost;
- грешен marker ID;
- нестабилна детекция;
- RZ извън разрешените граници;
- error нараства в няколко последователни итерации;
- заявената корекция надвишава allowed range;
- достигнат е `max_iterations`;
- robot motion error;
- collision/safety condition;
- camera frame timeout;
- промяна на work-object/camera calibration по време на процедурата.

След abort:

```text
AUTO ALIGN FAILED

Operator intervention required.
```

---

## 19. Камера върху робота

Ако камерата е монтирана върху робота, всяко движение на робота променя и camera pose.

Поради това не трябва да се работи само с pixel difference от предишния кадър.

След всяко движение:

1. прави се нова детекция;
2. пресмята се отново текущото marker/robot отношение;
3. изчислява се нова грешка спрямо reference.

Тоест:

```text
reference marker <-> robot relationship
-
current marker <-> robot relationship
=
alignment error
```

Практическото изчисление използва frame chain-а от секция 2.1 и robot pose, синхронизиран с всеки frame. Между итерациите трябва да има motion complete, settle time и отхвърляне на всички кадри, заснети преди завършване на движението.

---

## 20. Препоръчителен операторски workflow

### Нормална работа

```text
Load/prepare shaft
      |
      v
Quick Verify
      |
  +---+---+
  |       |
 OK      NOT OK
  |       |
Paint    Align Shaft
```

### Align Shaft

```text
Live camera
    |
ArUco detection
    |
Operator guidance
    |
Coarse alignment
    |
Optional automatic fine alignment
    |
Stable verification
    |
READY
```

### Референтна калибрация

```text
Manual precise robot/shaft alignment
       |
Stable marker detection
       |
Create Initial Reference / Replace Reference
       |
Save calibration
       |
Verify
```

---

## 21. Operator Dashboard

Препоръчителни бутони:

```text
[ Align Shaft ]
[ Verify Shaft ]
[ Create Initial Reference ]
[ Replace Reference ]
[ Auto Fine Align ]
```

Операциите за създаване и замяна на референция трябва да са защитени.

Възможни варианти:

- достъп само в calibration/maintenance mode;
- confirmation dialog;
- показване на стара и нова референция;
- записване на timestamp;
- логване на оператора, ако системата има user accounts.

---

## 22. Dashboard информация

Live alignment view:

```text
Marker ID:             17
Marker detected:       YES
Stable:                YES

X error:               +0.31 mm
Y error:               -0.18 mm
XY error:               0.36 mm

RZ error:               ignored / +1.2 deg

State:                 ALIGNED
```

При бъдещ RZ support:

```text
TRANSLATION
← X: 2.8 mm
↑ Y: 1.2 mm

ROTATION
↺ RZ: 1.7°
```

---

## 23. Suggested data model

```yaml
shaft_alignment:
  schema_version: 1

  marker:
    dictionary: DICT_6X6_250
    id: 17
    size_mm: ...

  reference:
    t_marker_paint_ref: [... 4x4 homogeneous transform ...]

    robot_pose:
      x_mm: ...
      y_mm: ...
      z_mm: ...
      rx_deg: ...
      ry_deg: ...
      rz_deg: ...

    calibrated_at: ...
    calibrated_by: ...

    provenance:
      camera_serial: ...
      intrinsics_fingerprint: ...
      hand_eye_fingerprint: ...
      platform_frame_fingerprint: ...
      tool_frame_id: ...

  verification:
    pose_name: shaft_verification_pose
    settle_time_s: ...
    max_frame_age_ms: ...
    max_pose_sync_delta_ms: ...
    validity_window_ms: ...

  thresholds:
    reference_capture_xy_mm: 5.0
    verify_xy_mm: 0.5
    aligned_enter_xy_mm: 0.5
    aligned_leave_xy_mm: 0.8

    rz_warning_deg: null
    rz_reject_deg: null

  auto_align:
    enabled: true
    max_initial_xy_error_mm: 5.0
    gain: 0.5
    max_step_mm: 1.0
    fine_step_mm: 0.2
    tolerance_mm: 0.3
    max_iterations: 10

  stability:
    required_frames: 10
    max_spread_mm: 0.2
    max_reprojection_error_px: ...
```

Threshold/config settings и calibration record трябва да се пазят отделно. Промяна на tuning threshold не трябва да пренаписва референтната трансформация. Calibration record се маркира `STALE`, ако някой provenance fingerprint вече не съвпада.

---

## 24. API / Backend операции

Примерни операции:

```text
start_shaft_alignment()
stop_shaft_alignment()

get_shaft_alignment_status()

create_initial_shaft_reference()
replace_shaft_reference(expected_reference_version)

verify_shaft_alignment()

run_auto_fine_alignment()
```

Примерен status:

```json
{
  "marker_detected": true,
  "marker_id": 17,
  "stable": true,

  "error_x_mm": 0.18,
  "error_y_mm": -0.12,
  "error_xy_mm": 0.22,

  "error_rz_deg": null,

  "within_xy_tolerance": true,
  "within_rz_tolerance": true,

  "reference_valid": true,
  "reference_version": 3,
  "verified_at": "...",
  "expires_at": "...",
  "ready_to_paint": true
}
```

Mutating operations трябва да използват reference version/optimistic concurrency check, за да не може остарял UI status да презапише по-нова референция.

---

## 25. Paint execution integration

Paint trajectory не трябва да разчита, че UI вече е направил проверката.

Backend execution flow:

```text
execute_paint_trajectory()
        |
        v
validate reference
        |
        v
quick shaft verification
        |
        v
validate XY/RZ
        |
    +---+---+
    |       |
   PASS    FAIL
    |       |
execute   reject
```

Gate-ът се поставя в paint execution state machine непосредствено преди първото paint действие. UI бутонът `Verify Shaft` е диагностичен/операторски shortcut и никога не заобикаля backend gate-а.

При reject трябва да се върне ясна причина:

```text
SHAFT_ALIGNMENT_INVALID
MARKER_NOT_FOUND
SHAFT_XY_OUT_OF_TOLERANCE
SHAFT_RZ_OUT_OF_TOLERANCE
SHAFT_REFERENCE_NOT_CALIBRATED
SHAFT_DETECTION_UNSTABLE
SHAFT_VERIFICATION_EXPIRED
SHAFT_CALIBRATION_STALE
SHAFT_FRAME_POSE_MISMATCH
```

---

## 25.1. Архитектурно разпределение

Функционалността е paint-specific и се композира от `PaintRobotSystem`:

```text
src/robot_systems/paint/
  shaft_alignment/
    i_shaft_alignment_service.py
    shaft_alignment_service.py
    models.py
    reference_serializer.py

  applications/shaft_alignment/
    service/          <- тесен application contract
    model/
    view/
    controller/

  processes/paint/execution_machine/
    VERIFY_SHAFT_ALIGNMENT state/handler
```

Отговорности:

- `ShaftAlignmentService`: sampling, frame transforms, filtering, reference persistence, verification и bounded auto-alignment orchestration;
- alignment application: само операторски команди и визуализация през application service interface;
- paint execution state machine: задължителният verification gate;
- engine vision: само общи camera/ArUco primitives без shaft/paint semantics;
- общият `MotionService`: непроменен и без paint-specific правила.

Блокиращите camera и robot операции се изпълняват извън `BaseProcess` lifecycle lock. UI ги стартира през `QThread + _Worker` или получава progress през broker callbacks с `_Bridge(QObject)`; всички subscriptions се unsubscribe-ват в `stop()`.

---

## 26. Диагностика и логване

При всяка проверка е полезно да се записват:

```text
timestamp
marker_id

current marker/paint transform
reference marker/paint transform

error_x/y
error_xy

rz / error_rz

number_of_samples
measurement_spread

verification_result
```

При auto fine alignment:

```text
iteration
measured_error
requested_correction
actual_robot_pose
result
```

Това ще бъде много полезно при настройване на tolerance-ите и анализ на точността.

---

## 27. Валидационни тестове

Числата в този план (`0.2 mm`, `0.5 mm`, `10 frames` и други) са начални experimental values, а не гарантирана точност. Production threshold се приема само след measurement-system analysis.

Минимално acceptance правило:

```text
vision_acceptance_bound_mm =
    max(3 * repeatability_sigma_mm, systematic_error_bound_mm)

Системата е подходяща само ако:
vision_acceptance_bound_mm <= process_required_tolerance_mm
```

Production `verify_xy_mm` не трябва да е по-малък от доказаната measurement uncertainty. Ако един ArUco marker не покрива изискването, следващата стъпка е по-голям marker или rigid multi-marker board; допълнително филтриране само по себе си не премахва systematic error.

### 27.1. Repeatability test

Без движение на вала:

- 50-100 измервания;
- average X/Y;
- min/max;
- standard deviation;
- peak-to-peak spread.

Цел:

да се определи реалният noise floor на vision системата.

### 27.2. Known displacement test

Преместване на вала с известни стойности:

```text
+1 mm X
+2 mm X
-1 mm Y
+5 mm Y
```

Сравняване на:

```text
physical movement
vs
detected movement
```

Тестът задължително проверява sign и axis mapping за `+X`, `-X`, `+Y`, `-Y`, както в platform frame, така и в robot/base frame. Измерва се systematic error, а не само repeatability.

### 27.3. Workspace test

Проверка на различни XY позиции в разрешения работен диапазон.

Цел:

да се провери дали грешката не нараства в краищата на изображението.

### 27.4. Auto alignment convergence test

Стартиране от:

```text
1 mm
2 mm
3 mm
5 mm
```

и проверка:

- брой итерации;
- overshoot;
- final error;
- repeatability.

Този тест се разрешава едва след dry-run тест, който доказва, че корекцията се прилага върху реално изпълняваната paint trajectory и не се губи при преминаване от camera pose към paint start pose.

### 27.5. Freshness и synchronization test

- стар camera frame след достигане на verification pose се отхвърля;
- frame/robot-pose pair извън `max_pose_sync_delta_ms` се отхвърля;
- verification изтича след `validity_window_ms`;
- движение на робота или calibration change инвалидира verification;
- restart поведение се проверява за `VALID` срещу `STALE` reference.

### 27.6. Failure-injection и safety test

- marker lost по време на sampling и между auto-align итерации;
- грешен marker ID;
- camera timeout/disconnect;
- robot motion reject/fault;
- calibration fingerprint mismatch;
- outlier frame и висок reprojection error;
- process stop/pause по време на verification;
- гаранция, че при всеки fail paint output остава изключен.

---

## 28. Етапи на имплементация

### Phase 0 — Contracts и measurement feasibility

- фиксиране на frame notation и transform direction;
- избор на `shaft_verification_pose`, settle time и freshness limits;
- избор как runtime paint frame променя реалната trajectory;
- repeatability, systematic-error и workspace measurements;
- решение single marker срещу rigid multi-marker board;
- acceptance criteria спрямо process tolerance-а.

### Phase 1 — ArUco XY detection

- детекция на shaft marker;
- marker center;
- конвертиране към физически XY;
- live debug values;
- записване на repeatability.
- timestamped robot-pose synchronization;
- reprojection/detection quality;
- отхвърляне на stale frames.

### Phase 2 — Reference calibration

- използване на съществуващата shaft/paint reference pose;
- отделни `Create Initial Reference` и `Replace Reference` операции;
- persistent calibration record;
- provenance fingerprints и invalidation;
- calculate current alignment error.

### Phase 3 — Operator guidance

- live camera view;
- XY arrows;
- magnitude;
- aligned/not aligned state;
- filtering;
- hysteresis.

### Phase 4 — Quick Verify

- backend `verify_shaft_alignment`;
- движение до verification pose, settle и fresh-frame gate;
- stable multi-frame detection;
- интеграция като state в paint execution machine;
- block execution on fail.

### Phase 5 — ChArUco work-object alignment

- автоматично определяне на paint platform frame;
- премахване/намаляване на manual work-object calibration;
- проверка на XY accuracy спрямо platform frame.

### Phase 6 — Automatic fine XY alignment

- prerequisite: доказан runtime paint-frame/trajectory contract;
- малки bounded robot corrections;
- detect -> correct -> detect loop;
- gain;
- adaptive step;
- convergence checks;
- abort conditions.

### Phase 7 — RZ validation

- извличане на shaft RZ;
- reference RZ;
- shortest-angle error;
- warning/reject boundaries;
- operator rotation guidance.

### Phase 8 — RZ compensation

- rotation на reference XY offset;
- преминаване към `T_marker_to_paint_reference`;
- optional automatic small RZ correction.

---

## 29. Препоръчителен първи milestone

Първата работеща версия не трябва да включва автоматично движение.

Цел:

```text
1. Detect ArUco
2. Capture reference
3. Move shaft manually
4. Show correct XY error
5. Guide operator back to reference
6. Verify repeatability
7. Block paint if outside tolerance
```

Едва след доказана XY точност да се включи:

```text
automatic fine robot correction
```

---

## 30. Краен очакван workflow

```text
                   ONE-TIME / MAINTENANCE

Manual accurate alignment
          |
          v
Detect shaft marker
          |
          v
Save reference relationship
          |
          v
Reference calibrated


                       PRODUCTION

Load shaft
    |
    v
Quick verification
    |
    +----------------------+
    |                      |
  within                outside
 tolerance              tolerance
    |                      |
    v                      v
  PAINT              Interactive Align
                           |
                           v
                    Operator coarse move
                           |
                           v
                    Auto fine alignment
                           |
                           v
                       Verify
                           |
                           v
                         PAINT
```

---

## 31. Основен принцип

Референтната калибрация не казва:

> „Валът винаги трябва да бъде на тази абсолютна позиция.“

Тя казва:

> „Когато роботът и валът са физически подравнени правилно, това е правилното отношение между ArUco маркера и paint/robot reference frame.“

След това системата просто се опитва да възстанови същото отношение автоматично.

Това позволява едно прецизно ръчно подравняване да се използва като ground-truth за последваща автоматизация.
