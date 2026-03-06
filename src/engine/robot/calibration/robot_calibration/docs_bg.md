# Модул за Калибриране на Робот - Изчерпателна Документация

**Версия:** 5.0  
**Дата:** Декември 2025  
**Път на Модула:** `/src/modules/robot_calibration`

---

## Съдържание

1. [Общ Преглед](#общ-преглед)
2. [Архитектура](#архитектура)
3. [Дизайн на Машината на Състоянията](#дизайн-на-машината-на-състоянията)
4. [Дефиниции на Състоянията](#дефиниции-на-състоянията)
5. [Контекст на Изпълнение](#контекст-на-изпълнение)
6. [Диаграми на Потока на Състоянията](#диаграми-на-потока-на-състоянията)
7. [Правила за Преход](#правила-за-преход)
8. [Ръководство за Употреба](#ръководство-за-употреба)
9. [Конфигурация](#конфигурация)
10. [Обработка на Грешки](#обработка-на-грешки)

---

## Общ Преглед

### Предназначение

Модулът за Калибриране на Робот извършва **калибриране на координатната система камера-робот** използвайки архитектура на машина на състоянията. Той установява пространствената трансформация между пикселните координати на камерата и координатите на работното пространство на робота чрез откриване на визуални маркери (шахматен модел и ArUco маркери) и изчисляване на хомографска матрица.

### Какво Прави

1. **Открива шахматен модел** за установяване на референтна координатна система
2. **Картографира осите на камерата към осите на робота** (автоматично калибриране на картографирането на осите)
3. **Открива множество ArUco маркери** поставени на известни позиции върху калибрационната плоча
4. **Итеративно подравнява робота** за центриране на всеки маркер в изгледа на камерата
5. **Записва съответстващи точки** (координати на камерата ↔ координати на робота)
6. **Изчислява хомографска матрица** за трансформация камера-робот
7. **Валидира точността на калибрирането** чрез анализ на грешката при обратна проекция

### Защо Съществува

Роботните системи за визия се нуждаят от точно пространствено калибриране за да:
- Преобразуват открити позиции на обекти от координати на камерата в координати на работното пространство на робота
- Позволяват прецизни операции вземане и поставяне
- Компенсират вариации в монтажа на камерата
- Отчитат изкривяване на лещата и ефекти на перспективата
- Адаптират се автоматично към различни конфигурации на робота

---

## Архитектура

### Основни Компоненти

```
robot_calibration/
├── newRobotCalibUsingExecutableStateMachine.py   # Главен оркестратор на конвейера
├── RobotCalibrationContext.py                     # Контекст на изпълнение (съхранение на състояние)
├── CalibrationVision.py                           # Алгоритми за компютърно зрение
├── robot_controller.py                            # Управление на движението на робота
├── config_helpers.py                              # Конфигурационни dataclass-ове
├── states/                                        # Имплементации на обработчици на състояния
│   ├── robot_calibration_states.py               # State enum и правила за преход
│   ├── state_result.py                           # Обвивка за резултат от състояние
│   ├── initializing.py                           # INITIALIZING състояние
│   ├── axis_mapping.py                           # AXIS_MAPPING състояние
│   ├── looking_for_chessboard_handler.py         # LOOKING_FOR_CHESSBOARD състояние
│   ├── chessboard_found_handler.py               # CHESSBOARD_FOUND състояние
│   ├── looking_for_aruco_markers_handler.py      # LOOKING_FOR_ARUCO_MARKERS състояние
│   ├── all_aruco_found_handler.py                # ALL_ARUCO_FOUND състояние
│   ├── compute_offsets_handler.py                # COMPUTE_OFFSETS състояние
│   ├── handle_height_sample_state.py             # SAMPLE_HEIGHT състояние
│   └── remaining_handlers.py                     # ALIGN_ROBOT, ITERATE_ALIGNMENT, DONE, ERROR
├── metrics.py                                     # Валидиране на калибрирането
├── logging.py                                     # Утилити за структурирано логване
├── debug.py                                       # Визуализация за отстраняване на грешки
└── visualizer.py                                  # Визуализация на живо предаване
```

### Дизайн Шаблон

**Изпълним Шаблон на Машина на Състоянията**
- Разделя логиката на състоянията от преходите между състоянията
- Всяко състояние е чиста функция: `(Context) → NextState`
- Контекстът съхранява всички променливи състояния
- Правилата за преход са декларативни и валидирани
- Обработчиците на състояния са тестваеми изолирано

---

## Дизайн на Машината на Състоянията

### Защо Машина на Състоянията?

Процесът на калибриране е по същество **последователен** и **зависим от условия**:
- Всяка стъпка зависи от успеха на предишните стъпки
- Някои състояния може да се нуждаят от повторен опит (напр. откриване на маркери)
- Грешки могат да се появят на всеки етап
- Ясните преходи между състоянията правят процеса одитируем

### Компоненти на Машината на Състоянията

#### 1. **Състояния (Enum)**
```python
class RobotCalibrationStates(Enum):
    INITIALIZING = auto()
    AXIS_MAPPING = auto()
    LOOKING_FOR_CHESSBOARD = auto()
    CHESSBOARD_FOUND = auto()
    LOOKING_FOR_ARUCO_MARKERS = auto()
    ALL_ARUCO_FOUND = auto()
    COMPUTE_OFFSETS = auto()
    ALIGN_ROBOT = auto()
    ITERATE_ALIGNMENT = auto()
    SAMPLE_HEIGHT = auto()
    DONE = auto()
    ERROR = auto()
```

#### 2. **Контекст (Споделено Състояние)**
- `RobotCalibrationContext`: Съхранява всички данни за калибриране, конфигурация и системни компоненти
- Предава се на всеки обработчик на състояние
- Модифицира се от обработчиците на състояния за напредък на калибрирането

#### 3. **Обработчици на Състояния (Функции)**
- Чисти функции: `handle_<state_name>(context) → NextState`
- Четат от контекста, извършват операции, модифицират контекста, връщат следващо състояние
- Няма странични ефекти извън модификацията на контекста

#### 4. **Правила за Преход (Декларативни)**
- Dict картографиране: `CurrentState → Set[ValidNextStates]`
- Налагат се от framework-а на машината на състоянията
- Невалидни преходи предизвикват грешки

#### 5. **ExecutableStateMachine (Оркестратор)**
- Управлява преходите между състоянията
- Валидира преходите спрямо правилата
- Извиква обработчиците на състоянията
- Излъчва промени в състоянията чрез message broker
- Обработва хронометраж и проследяване на производителността

---

## Дефиниции на Състоянията

### 1. INITIALIZING

**Цел:** Проверка, че системата на камерата е готова и инициализирана

**Контекст Чете:**
- `context.system` (VisionSystem)

**Контекст Записва:**
- Няма (само валидация)

**Логика:**
```python
if frame_provider is None:
    return INITIALIZING  # Остава в състоянието, камерата не е готова
else:
    return AXIS_MAPPING  # Камерата е готова, продължава
```

**Следващи Състояния:**
- `AXIS_MAPPING` (успех)
- `INITIALIZING` (повторен опит ако камерата не е готова)

**Условия за Грешка:** Няма (чака докато камерата е готова)

---

### 2. AXIS_MAPPING

**Цел:** Автоматично калибриране на картографирането между осите на изображението на камерата и осите на движение на робота

**Контекст Чете:**
- `context.system` (камера)
- `context.calibration_vision` (откриване на маркери)
- `context.calibration_robot_controller` (движение)

**Контекст Записва:**
- `context.image_to_robot_mapping` (ImageToRobotMapping обект)

**Логика:**
1. Открива референтен маркер (ID=4) на начална позиция → `(x1, y1)` пиксели
2. Движи робота **+100mm по ос X**
3. Открива маркера на нова позиция → `(x2, y2)` пиксели
4. Изчислява делта на изображението: `(Δx_img, Δy_img) = (x2-x1, y2-y1)`
5. Определя коя ос на изображението (X или Y) се е променила най-много → Робот X се картографира на тази ос на изображението
6. Определя посоката (PLUS или MINUS) на базата на корелация на знака
7. Движи робота обратно на начална позиция
8. Движи робота **-100mm по ос Y**
9. Повтаря откриване и анализ за картографиране на Робот Y
10. Създава `ImageToRobotMapping` обект с двете картографирания на осите

**Примерен Изход:**
```
Robot X: AxisMapping(image_axis=ImageAxis.X, direction=Direction.PLUS)
Robot Y: AxisMapping(image_axis=ImageAxis.Y, direction=Direction.PLUS)
```

Това означава:
- Robot +X → Image -X (защото посоката е PLUS и изображението се е движило негативно)
- Robot +Y → Image -Y

**Следващи Състояния:**
- `LOOKING_FOR_CHESSBOARD` (успех)
- `ERROR` (ако маркерът не е намерен или движението на робота е неуспешно)

**Условия за Грешка:**
- Маркер ID=4 не е видим след MAX_ATTEMPTS
- Командата за движение на робота е неуспешна
- Грешка в системата за визия

---

### 3. LOOKING_FOR_CHESSBOARD

**Цел:** Откриване на шахматен калибрационен модел за установяване на референтна координатна система и изчисляване на мащаб пиксели-на-милиметър

**Контекст Чете:**
- `context.system` (камера)
- `context.calibration_vision` (откриване на шахматна дъска)
- `context.chessboard_size` (размери на модела)
- `context.square_size_mm` (физически размер на квадрата)

**Контекст Записва:**
- `context.calibration_vision.PPM` (пиксели на милиметър)
- `context.bottom_left_chessboard_corner_px` (референтна точка в пиксели)

**Логика:**
1. Улавя кадър от камерата
2. Извиква `calibration_vision.find_chessboard_and_compute_ppm(frame)`
   - Използва OpenCV `cv2.findChessboardCorners()`
   - Изчислява разстояние между ъглите в пиксели
   - Дели на известно физическо разстояние → PPM
3. Запазва долния ляв ъгъл като референтна точка
4. Ако не е намерен, остава в състоянието (повторен опит на следваща итерация)

**Следващи Състояния:**
- `CHESSBOARD_FOUND` (моделът е открит)
- `LOOKING_FOR_CHESSBOARD` (повторен опит ако не е намерен)

**Условия за Грешка:** Няма (повтаря безкрайно докато не е намерен)

**Критични Данни:**
- **PPM (Пиксели на Милиметър):** Фактор на преобразуване от пикселни разстояния към реални милиметри
- **Долен Ляв Ъгъл:** Референтна точка (0,0) в координатната система на шахматната дъска

---

### 4. CHESSBOARD_FOUND

**Цел:** Преходно състояние потвърждаващо откриването на шахматната дъска

**Контекст Чете:**
- `context.chessboard_center_px`

**Контекст Записва:** Няма

**Логика:**
- Логва съобщение за потвърждение
- Незабавно преминава към следващото състояние

**Следващи Състояния:**
- `LOOKING_FOR_ARUCO_MARKERS` (винаги)

**Условия за Грешка:** Няма

---

### 5. LOOKING_FOR_ARUCO_MARKERS

**Цел:** Откриване на всички необходими ArUco маркери в изгледа на камерата

**Контекст Чете:**
- `context.system` (камера)
- `context.calibration_vision.required_ids` (множество от ID-та на маркери за намиране)
- `context.live_visualization` (флаг за визуализация)

**Контекст Записва:**
- `context.calibration_vision.detected_ids` (множество от намерени ID-та на маркери)
- `context.calibration_vision.marker_top_left_corners` (речник: marker_id → (x, y) пиксели)

**Логика:**
1. Изчиства буфера на камерата (отхвърля стари кадри)
2. Улавя свеж кадър
3. Извиква `calibration_vision.find_required_aruco_markers(frame)`
   - Използва OpenCV `cv2.aruco.detectMarkers()`
   - Проверява дали всички необходими ID-та са налични
4. Показва визуализация на живо предаване (опционално)
5. Ако всички маркери са намерени → продължава
6. Ако не всички са намерени → повторен опит

**Следващи Състояния:**
- `ALL_ARUCO_FOUND` (всички необходими маркери са открити)
- `LOOKING_FOR_ARUCO_MARKERS` (повторен опит ако е непълно)

**Условия за Грешка:** Няма (повтаря безкрайно)

**Бележка за Производителност:** Използва фонова нишка за неблокираща визуализация

---

### 6. ALL_ARUCO_FOUND

**Цел:** Обработка на открити маркери и преобразуване на координати в милиметри

**Контекст Чете:**
- `context.calibration_vision.marker_top_left_corners` (пиксели)
- `context.calibration_vision.PPM` (фактор на преобразуване)
- `context.bottom_left_chessboard_corner_px` (референтна точка)

**Контекст Записва:**
- `context.calibration_vision.marker_top_left_corners_mm` (речник: marker_id → (x_mm, y_mm))
- `context.camera_points_for_homography` (копие на пикселни координати)

**Логика:**
За всеки открит маркер:
```python
x_mm = (marker_x_px - bottom_left_x_px) / PPM
y_mm = (marker_y_px - bottom_left_y_px) / PPM
```

**Следващи Състояния:**
- `COMPUTE_OFFSETS` (винаги)

**Условия за Грешка:** Няма (данните вече са валидирани в предишното състояние)

---

### 7. COMPUTE_OFFSETS

**Цел:** Изчисляване на отместването на всеки маркер от центъра на изображението (в милиметри)

**Контекст Чете:**
- `context.calibration_vision.marker_top_left_corners_mm`
- `context.system.camera_settings` (размери на изображението)
- `context.bottom_left_chessboard_corner_px`
- `context.calibration_vision.PPM`

**Контекст Записва:**
- `context.markers_offsets_mm` (речник: marker_id → (offset_x_mm, offset_y_mm))

**Логика:**
1. Взема центъра на изображението в пиксели: `(width/2, height/2)`
2. Преобразува центъра на изображението в mm спрямо шахматната дъска:
   ```python
   center_x_mm = (center_x_px - bottom_left_x_px) / PPM
   center_y_mm = (center_y_px - bottom_left_y_px) / PPM
   ```
3. За всеки маркер изчислява отместване от центъра на изображението:
   ```python
   offset_x_mm = marker_x_mm - center_x_mm
   offset_y_mm = marker_y_mm - center_y_mm
   ```

**Следващи Състояния:**
- `ALIGN_ROBOT` (успех)
- `ERROR` (ако липсват PPM или данни за шахматната дъска)

**Условия за Грешка:**
- `PPM is None` (откриването на шахматната дъска е било неуспешно по-рано)
- `bottom_left_chessboard_corner_px is None`

**Защо Отместванията Са Важни:** Тези отмествания казват на робота колко далеч да се движи, за да центрира всеки маркер в изгледа на камерата

---

### 8. ALIGN_ROBOT

**Цел:** Движене на робота за приблизително подравняване с текущия маркер

**Контекст Чете:**
- `context.required_ids` (сортиран списък от маркери)
- `context.current_marker_id` (индекс в сортирания списък)
- `context.markers_offsets_mm` (целеви отмествания)
- `context.image_to_robot_mapping` (картографиране на осите)
- `context.calibration_robot_controller` (движение)
- `context.Z_target` (целева Z височина)

**Контекст Записва:**
- `context.iteration_count = 0` (нулиране за нов маркер)

**Логика:**
1. Взема текущото ID на маркера от сортирания списък
2. Взема отместването на маркера от центъра на изображението (в mm)
3. Прилага картографиране на осите за преобразуване на отмествания на изображението → отмествания на робота:
   ```python
   robot_offset = image_to_robot_mapping.map(offset_x_mm, offset_y_mm)
   ```
4. Изчислява текущата позиция на робота спрямо калибрационната позиция
5. Изчислява целева позиция:
   ```python
   new_x = current_x + (marker_offset_x - current_offset_x)
   new_y = current_y + (marker_offset_y - current_offset_y)
   new_z = Z_target
   ```
6. Движи робота до целевата позиция (блокиращо)
7. Ако движението е неуспешно, повторен опит от предишната успешна позиция
8. Чака 1 секунда за стабилизация

**Следващи Състояния:**
- `ITERATE_ALIGNMENT` (движението е успешно)
- `ERROR` (движението е неуспешно след повторен опит)

**Условия за Грешка:**
- Движението на робота връща ненулев код за грешка
- Превишени са границите на безопасност
- Неуспешна комуникация с робота

**Логика за Повторен Опит:** Ако първото движение е неуспешно, връща се към последната известна добра позиция, след което повторен опит

---

### 9. ITERATE_ALIGNMENT

**Цел:** Итеративно рафиниране на позицията на робота докато маркерът не бъде центриран в изображението в рамките на прага

**Контекст Чете:**
- `context.current_marker_id`
- `context.iteration_count`
- `context.max_iterations` (по подразбиране: 50)
- `context.alignment_threshold_mm` (целева прецизност)
- `context.system` (камера)
- `context.calibration_vision` (откриване на маркери)
- `context.image_to_robot_mapping` (картографиране на осите)
- `context.ppm_scale` (фактор на корекция за Z-височина)

**Контекст Записва:**
- `context.iteration_count` (увеличен)
- `context.robot_positions_for_calibration[marker_id]` (при успех)
- `context.calibration_error_message` (при грешка)

**Логика:**
1. **Проверка на лимита на итерации:**
   ```python
   if iteration_count > max_iterations:
       return ERROR  # Неуспешна конвергенция
   ```

2. **Улавяне и откриване на маркер:**
   - Взема свеж кадър от камерата
   - Открива специфичен маркер използвайки `detect_specific_marker(frame, marker_id)`
   - Ако не е намерен → остава в състоянието (повторен опит)

3. **Изчисляване на грешка при подравняване:**
   ```python
   image_center = (width/2, height/2)
   marker_position = marker_top_left_corner_px
   offset_px = marker_position - image_center
   error_px = sqrt(offset_x² + offset_y²)
   
   # Коригира PPM за текущата Z-височина
   adjusted_PPM = PPM * ppm_scale
   error_mm = error_px / adjusted_PPM
   ```

4. **Проверка дали е подравнен:**
   ```python
   if error_mm <= alignment_threshold_mm:
       # Успех! Запазва позицията на робота
       robot_positions_for_calibration[marker_id] = get_current_position()
       return SAMPLE_HEIGHT  # Измерва височина на тази позиция
   ```

5. **Изчисляване на коригиращо движение:**
   - Преобразува пикселни отмествания в mm: `offset_mm = offset_px / adjusted_PPM`
   - Прилага картографиране на осите: `robot_offset_mm = image_to_robot_mapping.map(offset_x_mm, offset_y_mm)`
   - Изчислява итеративна позиция с адаптивно скалиране (вижте по-долу)
   - Движи робота до нова позиция (блокиращо)
   - Чака за стабилизация

6. **Адаптивно Скалиране на Движението:**
   ```python
   # Скалира движението на базата на величината на грешката
   normalized_error = min(error_mm / max_error_ref, 1.0)
   step_scale = tanh(k * normalized_error)
   max_move = min_step + step_scale * (max_step - min_step)
   
   # Близо до целта, прилага амортизация за предотвратяване на надхвърляне
   if error_mm < threshold * 2:
       damping = (error_mm / (threshold * 2))²
       max_move *= max(damping, 0.05)
   
   # Производно управление (анти-надхвърляне)
   if has_previous_error:
       error_change = current_error - previous_error
       derivative_factor = 1.0 / (1.0 + derivative_scaling * abs(error_change))
       max_move *= derivative_factor
   ```

**Следващи Състояния:**
- `ITERATE_ALIGNMENT` (още не е подравнен, повторен опит)
- `SAMPLE_HEIGHT` (подравнен, измерва височина)
- `ERROR` (превишени са максималните итерации или движението е неуспешно)

**Условия за Грешка:**
- `iteration_count > max_iterations` → Калибрирането е неуспешно, маркерът не може да бъде подравнен
- Маркерът не е открит по време на итерация (остава в състоянието)
- Движението на робота е неуспешно (връща ERROR)

**Хронометраж на Производителност:** Проследява capture_time, detection_time, processing_time, movement_time, stability_time

---

### 10. SAMPLE_HEIGHT

**Цел:** Измерване на височината на работната повърхност на текущата подравнена позиция използвайки лазерно откриване

**Контекст Чете:**
- `context.height_measuring_service` (лазерен датчик за височина)
- `context.calibration_robot_controller.robot_service` (текуща позиция)

**Контекст Записва:**
- Измерени данни за височина (логнати, в момента не се съхраняват в контекста)

**Логика:**
1. Взема текущата позиция на робота `(x, y, z, rx, ry, rz)`
2. Извиква `height_measuring_service.measure_at(x, y)`
3. Получава `(height_mm, pixel_data)`
4. Логва измерването

**Следващи Състояния:**
- `DONE` (винаги)

**Условия за Грешка:** Няма (измерванията се логват, но не влияят на потока на калибриране)

**Бъдещо Подобрение:** Съхранява измервания на височина в контекста за профилиране на повърхността

---

### 11. DONE

**Цел:** Управление на прехода между маркери и финално завършване

**Контекст Чете:**
- `context.current_marker_id`
- `context.required_ids` (общ брой маркери)

**Контекст Записва:**
- `context.current_marker_id` (увеличен ако остават още маркери)

**Логика:**
```python
if current_marker_id < len(required_ids) - 1:
    current_marker_id += 1
    return ALIGN_ROBOT  # Обработва следващ маркер
else:
    return DONE  # Всички маркери са завършени, финализира
```

**Следващи Състояния:**
- `ALIGN_ROBOT` (още маркери за обработка)
- `DONE` (финално завършване - машината на състоянията спира)

**Условие за Спиране на Машината на Състоянията:**
Когато `DONE` е върнат и всички маркери са обработени, главният конвейер открива това и извиква `state_machine.stop_execution()`

---

### 12. ERROR

**Цел:** Обработка на неуспех при калибриране, логване на детайли, известяване на UI, спиране на процеса

**Контекст Чете:**
- `context.calibration_error_message` (детайлно описание на грешката)
- `context.current_marker_id`
- `context.iteration_count`
- `context.robot_positions_for_calibration` (успешни маркери)
- `context.broadcast_events` (флаг за известяване на UI)

**Контекст Записва:**
- Няма (терминално състояние)

**Логика:**
1. Извлича специфично съобщение за грешка от контекста (или използва по подразбиране)
2. Логва детайлна грешка с контекст:
   - Кой маркер е неуспешен
   - Текущ брой итерации
   - Колко маркера са успешно калибрирани
3. Ако UI събитията са активирани:
   - Създава структурирано известие за грешка JSON
   - Публикува към `CALIBRATION_STOP_TOPIC` чрез message broker
4. Остава в ERROR състояние (терминално)

**Структура на Известие за Грешка:**
```json
{
  "status": "error",
  "message": "Robot movement failed during fine alignment of marker 2.",
  "details": {
    "current_marker": 2,
    "total_markers": 4,
    "successful_markers": 1,
    "iteration_count": 15,
    "max_iterations": 50
  }
}
```

**Следващи Състояния:**
- `ERROR` (остава в състоянието, машината на състоянията спира)

**Кога ERROR се Задейства:**
- Движението на робота е неуспешно (след повторни опити)
- Превишени са максималните итерации без конвергенция
- Липсват критични данни за калибриране (PPM, шахматна дъска)
- Грешки в системата за визия
- Всяко необработено изключение в обработчиците на състояния

---

## Контекст на Изпълнение

### RobotCalibrationContext

Контекстът на изпълнение е **контейнер на споделено състояние**, който се предава на всеки обработчик на състояние. Той съхранява всички данни необходими по време на калибриране.

#### Системни Компоненти

```python
context.vision_service  # VisionSystem (интерфейс на камера)
context.height_measuring_service  # Лазерен датчик за височина
context.calibration_robot_controller  # Обвивка за управление на движението на робота
context.calibration_vision  # Алгоритми за компютърно зрение
context.debug_draw  # Помощник за визуализация при отстраняване на грешки
context.broker  # MessageBroker за UI събития
context.state_machine  # Референция към машината на състоянията
```

#### Конфигурация
```python
context.required_ids                    # Множество от ArUco маркер ID-та за калибриране
context.chessboard_size                 # (cols, rows) tuple
context.square_size_mm                  # Физически размер на квадратите на шахматната дъска
context.alignment_threshold_mm          # Целева прецизност (по подразбиране: 1.0mm)
context.max_iterations                  # Макс. итерации на рафиниране (по подразбиране: 50)
context.debug                           # Активиране на debug изходи
context.step_by_step                    # Пауза между стъпки
context.live_visualization              # Показване на камерно предаване
context.broadcast_events                # Изпращане на UI известия
```

#### Състояние на Калибриране
```python
context.bottom_left_chessboard_corner_px  # Референтна точка (x, y) в пиксели
context.chessboard_center_px              # Център на шахматната дъска (x, y) в пиксели
context.markers_offsets_mm                # Речник: marker_id → (offset_x_mm, offset_y_mm)
context.current_marker_id                 # Индекс на текущия маркер който се подравнява
context.iteration_count                   # Текуща итерация на рафиниране
```

#### Конфигурация на Z-Ос
```python
context.Z_current                       # Z позиция на робота при начало на калибриране
context.Z_target                        # Целева Z височина по време на калибриране
context.ppm_scale                       # Z_current / Z_target (фактор за корекция на PPM)
```

#### Резултати от Калибриране
```python
context.robot_positions_for_calibration  # Речник: marker_id → [x, y, z, rx, ry, rz]
context.camera_points_for_homography     # Речник: marker_id → (x_px, y_px)
context.image_to_robot_mapping           # ImageToRobotMapping (картографиране на осите)
```

#### Проследяване на Производителност
```python
context.state_timings                   # Речник: state_name → [duration1, duration2, ...]
context.current_state_start_time        # Времеви печат кога текущото състояние е започнало
context.total_calibration_start_time    # Времеви печат кога калибрирането е започнало
```

#### Методи
```python
context.start_state_timer(state_name)   # Започва хронометраж на състояние
context.end_state_timer()               # Завършва хронометраж на текущо състояние
context.flush_camera_buffer()           # Отхвърля стари кадри от камерата
context.get_current_state_name()        # Взема име на състоянието като string
context.to_debug_dict()                 # Сериализира в dict за отстраняване на грешки
context.reset()                         # Нулира до начално състояние
```

---

## Диаграми на Потока на Състоянията

### Високо-Ниво Поток на Калибриране

```
┌─────────────────┐
│  INITIALIZING   │  Чака камерата да е готова
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AXIS_MAPPING   │  Калибрира осите изображение-робот
└────────┬────────┘
         │
         ▼
│ LOOKING_FOR_CHESSBOARD  │◄─┐ Повторен опит докато не е намерена
└────────┬────────────────┘  │
         │ Намерена          │
         ▼                   │
┌─────────────────────┐      │
│  CHESSBOARD_FOUND   │      │ Не е намерена
└────────┬────────────┘      │
         │                   │
         ▼                   │
┌──────────────────────────┐ │
│ LOOKING_FOR_ARUCO_MARKERS│◄┘ Повторен опит докато всички не са намерени
└────────┬─────────────────┘
         │ Всички намерени
         ▼
┌─────────────────────┐
│  ALL_ARUCO_FOUND    │  Преобразува в mm координати
└────────┬────────────┘
         │
         ▼
┌─────────────────┐
│ COMPUTE_OFFSETS │  Изчислява отмествания на маркери от центъра
└────────┬────────┘
         │
         ▼
    ┌────────────────────────────────┐
    │   ЗА ВСЕКИ МАРКЕР (Цикъл)      │
    │                                 │
    │  ┌──────────────┐              │
    │  │ ALIGN_ROBOT  │  Начално движение│
    │  └──────┬───────┘              │
    │         │                       │
    │         ▼                       │
    │  ┌──────────────────┐          │
    │  │ ITERATE_ALIGNMENT│◄─┐       │
    │  └──────┬───────────┘  │       │
    │         │ Не е подравнен│      │
    │         │ Рафинира движение ─┘ │
    │         │ Подравнен            │
    │         ▼                       │
    │  ┌──────────────┐              │
    │  │SAMPLE_HEIGHT │  Измерва Z   │
    │  └──────┬───────┘              │
    │         │                       │
    │         ▼                       │
    │  ┌──────────────┐              │
    │  │     DONE     │              │
    │  └──────┬───────┘              │
    │         │                       │
    └─────────┼───────────────────────┘
              │ Още маркери? → ALIGN_ROBOT
              │ Всичко завършено? → DONE (финално)
              ▼
    ┌─────────────────┐
    │  DONE (финално) │  Изчислява хомография, запазва матрица
    └─────────────────┘

         Всяка грешка
              ↓
    ┌─────────────────┐
    │      ERROR      │  Логва, известява UI, спира
    └─────────────────┘
```

### Детайлен Цикъл на Итерация (На Маркер)

```
                  ┌──────────────┐
                  │ ALIGN_ROBOT  │
                  └──────┬───────┘
                         │
                         │ 1. Взема отместване на маркера от центъра на изображението
                         │ 2. Прилага картографиране на осите
                         │ 3. Изчислява целева позиция
                         │ 4. Движи робота (груба подравняване)
                         │
                         ▼
                  ┌──────────────────┐
             ┌────┤ ITERATE_ALIGNMENT├────┐
             │    └──────────────────┘    │
             │                             │
             │ 1. Улавя кадър             │
             │ 2. Открива маркер          │ Маркерът не е намерен → повторен опит
             │ 3. Изчислява error_mm      │
             │                             │
             │    error_mm ≤ праг?         │
             │           │                 │
             │          ДА                 │
             │           │                 │
             │           ▼                 │
             │    ┌──────────────┐        │
             │    │SAMPLE_HEIGHT │        │
             │    └──────┬───────┘        │
             │           │                 │
             │           ▼                 │
             │    ┌──────────────┐        │
             │    │     DONE     │        │ Макс. итерации
             │    └──────────────┘        │ превишени?
             │                             │    │
             │                             │   ДА
             │          НЕ                 │    │
             │           │                 │    ▼
             │           ▼                 │ ┌───────┐
             │    4. Изчислява движение   │ │ ERROR │
             │    5. Прилага адаптивно    │ └───────┘
             │       скалиране            │
             │    6. Движи робота ────────┘
             │       (фина корекция)
             │    7. Чака за стабилност
             │
             └──► Обратно към стъпка 1 (следваща итерация)
```

### Дърво на Решения за Избор на Следващо Състояние

```
ITERATE_ALIGNMENT:
│
├─ iteration_count > max_iterations? ──ДА──► ERROR
│                                              (calibration_error_message зададено)
├─ НЕ
│
├─ Маркер открит?
│  ├─ НЕ ──────────────────────────────────► ITERATE_ALIGNMENT (повторен опит)
│  │
│  └─ ДА
│     │
│     └─ Изчислява error_mm
│        │
│        ├─ error_mm ≤ alignment_threshold? ──ДА──► SAMPLE_HEIGHT
│        │                                            (съхранява позиция на робота)
│        │
│        └─ НЕ
│           │
│           └─ Движението на робота успешно?
│              ├─ ДА ──────────────────────► ITERATE_ALIGNMENT (следваща итерация)
│              │
│              └─ НЕ ────────────────────────► ERROR
│                                              (движението неуспешно)

SAMPLE_HEIGHT:
│
└─ Винаги ──────────────────────────────────► DONE

DONE:
│
├─ current_marker_id < total_markers - 1? ──ДА──► ALIGN_ROBOT
│                                                   (увеличава current_marker_id)
│
└─ НЕ ──────────────────────────────────────────► DONE (финално)
                                                   (спира машината на състоянията)
```

---

## Правила за Преход

### Пълна Таблица на Преходите

| Текущо Състояние            | Валидни Следващи Състояния                                            |
|----------------------------|-----------------------------------------------------------------------|
| `INITIALIZING`             | `AXIS_MAPPING`, `ERROR`                                               |
| `AXIS_MAPPING`             | `LOOKING_FOR_CHESSBOARD`, `ERROR`                                     |
| `LOOKING_FOR_CHESSBOARD`   | `CHESSBOARD_FOUND`, `LOOKING_FOR_CHESSBOARD` (повторен опит), `ERROR`|
| `CHESSBOARD_FOUND`         | `LOOKING_FOR_ARUCO_MARKERS`, `ALIGN_TO_CHESSBOARD_CENTER`, `ERROR`   |
| `ALIGN_TO_CHESSBOARD_CENTER` | `LOOKING_FOR_ARUCO_MARKERS`, `ERROR`                                |
| `LOOKING_FOR_ARUCO_MARKERS`| `ALL_ARUCO_FOUND`, `LOOKING_FOR_ARUCO_MARKERS` (повторен опит), `ERROR`|
| `ALL_ARUCO_FOUND`          | `COMPUTE_OFFSETS`, `ERROR`                                            |
| `COMPUTE_OFFSETS`          | `ALIGN_ROBOT`, `ERROR`                                                |
| `ALIGN_ROBOT`              | `ITERATE_ALIGNMENT`, `ERROR`                                          |
| `ITERATE_ALIGNMENT`        | `ITERATE_ALIGNMENT` (повторен опит), `SAMPLE_HEIGHT`, `ALIGN_ROBOT`, `DONE`, `ERROR` |
| `SAMPLE_HEIGHT`            | `DONE`, `ERROR`                                                       |
| `DONE`                     | `ALIGN_ROBOT` (следващ маркер), `DONE` (финално), `ERROR`            |
| `ERROR`                    | `ERROR` (терминално)                                                  |

### Налагане на Преходи

`ExecutableStateMachine` валидира всеки преход:

```python
def transition_to(self, next_state):
    current = self.current_state
    allowed = self.transition_rules[current]
    
    if next_state not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from {current} to {next_state}. "
            f"Allowed: {allowed}"
        )
    
    self.current_state = next_state
```

Това предотвратява:
- Логически грешки (пропускане на необходими състояния)
- Невалидни последователности на състояния
- Непредвидени преходи между състояния

---

## Ръководство за Употреба

### Основна Употреба

```python
from modules.robot_calibration.config_helpers import (
    RobotCalibrationConfig,
    AdaptiveMovementConfig,
    RobotCalibrationEventsConfig
)
from modules.robot_calibration.newRobotCalibUsingExecutableStateMachine import (
    RefactoredRobotCalibrationPipeline
)

# Конфигуриране на калибриране
config = RobotCalibrationConfig(
    vision_system=my_vision_system,
    robot_service=my_robot_service,
    height_measuring_service=my_laser_service,
    required_ids=[0, 1, 2, 3],  # ArUco маркер ID-та
    z_target=400.0,  # Целева Z височина в mm
    debug=False,
    step_by_step=False,
    live_visualization=True
)

# Конфигуриране на адаптивно движение (опционално)
adaptive_config = AdaptiveMovementConfig(
    target_error_mm=0.5,        # Целева прецизност
    min_step_mm=0.1,            # Минимално движение
    max_step_mm=10.0,           # Максимално движение
    max_error_ref=20.0,         # Грешка при макс стъпка
    k=1.5,                      # Отзивчивост
    derivative_scaling=0.3       # Анти-надхвърляне
)

# Конфигуриране на излъчване на събития (опционално)
events_config = RobotCalibrationEventsConfig(
    broker=message_broker,
    calibration_log_topic="calibration/log",
    calibration_start_topic="calibration/start",
    calibration_stop_topic="calibration/stop",
    calibration_image_topic="calibration/image"
)

# Създаване на конвейер
pipeline = RefactoredRobotCalibrationPipeline(
    config=config,
    adaptive_movement_config=adaptive_config,
    events_config=events_config
)

# Изпълнение на калибриране
success = pipeline.run()

if success:
    print("Калибрирането е успешно!")
    context = pipeline.get_context()
    print(f"Калибрирани {len(context.robot_positions_for_calibration)} маркера")
else:
    print("Калибрирането е неуспешно!")
    context = pipeline.get_context()
    print(f"Грешка: {context.calibration_error_message}")
```

### Достъп до Резултатите

```python
context = pipeline.get_context()

# Взема позициите на робота за всеки маркер
for marker_id, position in context.robot_positions_for_calibration.items():
    x, y, z, rx, ry, rz = position
    print(f"Маркер {marker_id}: ({x:.2f}, {y:.2f}, {z:.2f})")

# Взема точките на камерата
for marker_id, point in context.camera_points_for_homography.items():
    x_px, y_px = point
    print(f"Маркер {marker_id}: ({x_px:.2f}, {y_px:.2f}) пиксели")

# Взема статистики за времето
for state_name, durations in context.state_timings.items():
    avg_duration = sum(durations) / len(durations)
    print(f"{state_name}: {avg_duration:.2f}s средно")
```

### Мониторинг на Машината на Състоянията

```python
state_machine = pipeline.get_state_machine()

# Взема текущото състояние
current = state_machine.current_state
print(f"Текущо състояние: {current.name}")

# Проверка дали се изпълнява
if state_machine.is_running:
    print("Калибрирането е в процес...")
```

---

## Конфигурация

### RobotCalibrationConfig

| Параметър | Тип | Задължителен | Описание |
|-----------|------|----------|-------------|
| `vision_system` | VisionSystem | Да | Интерфейс на камера |
| `robot_service` | RobotService | Да | Интерфейс за управление на робота |
| `height_measuring_service` | HeightMeasuringService | Да | Лазерен датчик за височина |
| `required_ids` | List[int] | Да | ArUco маркер ID-та за калибриране |
| `z_target` | float | Да | Целева Z височина (mm) |
| `debug` | bool | Не | Активира debug изходи (по подразбиране: False) |
| `step_by_step` | bool | Не | Пауза между стъпки (по подразбиране: False) |
| `live_visualization` | bool | Не | Показва камерно предаване (по подразбиране: True) |

### AdaptiveMovementConfig

| Параметър | Тип | По подразбиране | Описание |
|-----------|------|---------|-------------|
| `target_error_mm` | float | 1.0 | Целева прецизност на подравняване (mm) |
| `min_step_mm` | float | 0.1 | Минимална стъпка на движение (mm) |
| `max_step_mm` | float | 10.0 | Максимална стъпка на движение (mm) |
| `max_error_ref` | float | 20.0 | Величина на грешката при макс стъпка (mm) |
| `k` | float | 1.5 | Фактор на отзивчивост (1.0=гладко, 2.0=агресивно) |
| `derivative_scaling` | float | 0.3 | Амортизация анти-надхвърляне |

### RobotCalibrationEventsConfig

| Параметър | Тип | Задължителен | Описание |
|-----------|------|----------|-------------|
| `broker` | MessageBroker | Да | Издател на събития |
| `calibration_log_topic` | str | Да | Topic за лог съобщения |
| `calibration_start_topic` | str | Да | Topic за събитие за стартиране |
| `calibration_stop_topic` | str | Да | Topic за събитие за спиране/грешка |
| `calibration_image_topic` | str | Да | Topic за изображения от камерата |

---

## Обработка на Грешки

### Категории Грешки

#### 1. **Системни Грешки**
- Камерата не е инициализирана → Чака в `INITIALIZING` състояние
- Неуспех на камерно предаване → Повторен опит на улавяне на кадър
- Неуспех на комуникация с робота → Преход към `ERROR`

#### 2. **Грешки при Откриване**
- Шахматната дъска не е намерена → Повторен опит в `LOOKING_FOR_CHESSBOARD`
- Не всички ArUco маркери са намерени → Повторен опит в `LOOKING_FOR_ARUCO_MARKERS`
- Маркер загубен по време на подравняване → Повторен опит в `ITERATE_ALIGNMENT`

#### 3. **Грешки при Движение**
- Движението на робота е неуспешно → Повторен опит веднъж, след това `ERROR`
- Превишени граници на безопасност → Незабавен `ERROR`
- Позицията е недостижима → `ERROR`

#### 4. **Грешки при Конвергенция**
- Превишени макс итерации → `ERROR` с детайлно съобщение
- Осцилация при подравняване → Обработва се от адаптивно движение + производно управление

#### 5. **Грешки в Данните**
- Липсващ PPM (откриването на шахматната дъска е неуспешно) → `ERROR` в `COMPUTE_OFFSETS`
- Невалидни данни за маркер → `ERROR` с описание

### Съобщения за Грешки

Всички грешки задават `context.calibration_error_message` с детайли:

```python
# Примерни съобщения за грешки
"Калибрирането е неуспешно по време на изчисляване на отместване. Липсват необходими данни: пиксели-на-mm (PPM). Откриването на шахматната дъска може да е било неуспешно."

"Движението на робота е неуспешно за маркер 2. Не може да достигне целевата позиция след повторен опит. Проверете границите на безопасност и границите на работното пространство на робота."

"Калибрирането е неуспешно: Не може да се подравни с маркер 3 след 50 итерации. Необходима прецизност: 1.0mm"

"Итеративното движение на робота е неуспешно за маркер 1 по време на итерация 23. Проверете свързаността на робота и системите за безопасност."
```

### UI Известия

Когато `broadcast_events=True`, грешките се публикуват към UI:

```json
{
  "status": "error",
  "message": "Could not align with marker 3 after 50 iterations",
  "details": {
    "current_marker": 3,
    "total_markers": 4,
    "successful_markers": 2,
    "iteration_count": 50,
    "max_iterations": 50
  }
}
```

### Стратегии за Възстановяване

| Тип Грешка | Възстановяване | Преход на Състояние |
|------------|----------|------------------|
| Неуспешно улавяне на кадър от камерата | Незабавен повторен опит | Остава в състоянието |
| Шахматната дъска не е открита | Безкраен повторен опит | `LOOKING_FOR_CHESSBOARD` |
| Маркерът не е открит | Безкраен повторен опит | `LOOKING_FOR_ARUCO_MARKERS` |
| Движението на робота е неуспешно (първи опит) | Повторен опит от последна позиция | Остава в състоянието |
| Движението на робота е неуспешно (втори опит) | Спиране на калибрирането | `ERROR` |
| Маркер загубен по време на итерация | Продължава да опитва | `ITERATE_ALIGNMENT` |
| Превишени макс итерации | Спиране на калибрирането | `ERROR` |

---

## Оптимизация на Производителността

### Изчистване на Буфера на Камерата

```python
context.min_camera_flush = 5  # Отхвърля 5 стари кадъра
```

Гарантира свежи, стабилни кадри за критични открития (шахматна дъска, маркери).

### Неблокираща Визуализация

Живото камерно предаване използва фонова нишка за да избегне блокиране на изпълнението на машината на състоянията.

### Адаптивно Движение

Прогресивно скалиране на движението:
- **Големи грешки** → Големи стъпки (бърза конвергенция)
- **Средни грешки** → Скалирани стъпки (балансирано)
- **Малки грешки** → Минимални стъпки с амортизация (прецизност)

Предотвратява:
- Бавна конвергенция (твърде предпазливо)
- Надхвърляне (твърде агресивно)
- Осцилация (производно управление)

### Хронометраж на Състоянията

Всяко изпълнение на състояние се хронометрира:
```python
context.state_timings = {
    'INITIALIZING': [0.15],
    'AXIS_MAPPING': [8.23],
    'LOOKING_FOR_CHESSBOARD': [0.42, 0.38],
    'ITERATE_ALIGNMENT': [0.25, 0.23, 0.21, 0.19, 0.18],
    ...
}
```

Използва се за:
- Анализ на производителността
- Идентификация на тесни места
- Оптимизация на калибрирането

---

## Изчисляване на Хомография (Финална Стъпка)

След като всички маркери са подравнени, конвейерът изчислява хомографската матрица:

```python
def _finalize_calibration(self):
    # Сортира по маркер ID
    sorted_robot_items = sorted(context.robot_positions_for_calibration.items())
    sorted_camera_items = sorted(context.camera_points_for_homography.items())
    
    # Извлича координати
    robot_positions = [pos[:2] for _, pos in sorted_robot_items]  # (x, y)
    camera_points = [pt for _, pt in sorted_camera_items]  # (x_px, y_px)
    
    # Изчислява хомография
    src_pts = np.array(camera_points, dtype=np.float32)
    dst_pts = np.array(robot_positions, dtype=np.float32)
    H, status = cv2.findHomography(src_pts, dst_pts)
    
    # Валидира
    avg_error, _ = metrics.test_calibration(H, src_pts, dst_pts)
    
    # Запазва ако е точно
    if avg_error <= 1.0:
        np.save(camera_to_robot_matrix_path, H)
        log_info("Калибрирането е успешно, матрицата е запазена")
    else:
        log_warning(f"Висока грешка ({avg_error:.2f}mm), препоръчва се повторно калибриране")
```

### Хомографска Матрица

3x3 хомографската матрица `H` трансформира координати на камерата в координати на робота:

```python
# Точка на камерата (в пиксели)
camera_point = [x_px, y_px, 1]

# Трансформация към координати на робота (в mm)
robot_point_homogeneous = H @ camera_point
robot_x = robot_point_homogeneous[0] / robot_point_homogeneous[2]
robot_y = robot_point_homogeneous[1] / robot_point_homogeneous[2]
```

---

## Отстраняване на Проблеми

### Калибрирането е Неуспешно при Откриване на Шахматна Дъска

**Симптоми:** Заседнало в `LOOKING_FOR_CHESSBOARD`

**Решения:**
1. Уверете се, че шахматната дъска е плоска, добре осветена, в изгледа на камерата
2. Проверете дали `chessboard_size` съответства на физическия модел
3. Проверете дали `square_size_mm` е правилен
4. Намалете блясъка/отраженията върху шахматната дъска
5. Уверете се, че фокусът на камерата е правилен

### Калибрирането е Неуспешно при Откриване на ArUco

**Симптоми:** Заседнало в `LOOKING_FOR_ARUCO_MARKERS`

**Решения:**
1. Уверете се, че всички необходими маркери са видими
2. Проверете дали ID-тата на маркерите съответстват на `required_ids`
3. Уверете се, че маркерите не са закрити
4. Проверете условията на осветление
5. Проверете качеството на печат на маркера (остри ръбове)

### Итерациите за Подравняване Никога Не Конвергират

**Симптоми:** `ERROR` с "max iterations exceeded"

**Решения:**
1. Увеличете `max_iterations` (по подразбиране: 50)
2. Разхлабете `alignment_threshold_mm` (напр., 1.5mm вместо 1.0mm)
3. Проверете прецизността на движение на робота
4. Проверете дали картографирането на осите е правилно (проверете AXIS_MAPPING логове)
5. Намалете `derivative_scaling` ако осцилира
6. Проверете стабилността на камерата (вибрации)

### Висока Грешка при Обратна Проекция

**Симптоми:** `avg_error > 1.0mm` след завършване на калибрирането

**Решения:**
1. Пуснете калибрирането отново
2. Проверете точността на поставяне на маркера
3. Проверете дали шахматната дъска е наистина плоска
4. Уверете се, че позициите на робота са били стабилни по време на подравняване
5. Проверете за изкривяване на лещата на камерата
6. Използвайте повече маркери (по-добро покритие на работното пространство)

### Неуспехи при Движение на Робота

**Симптоми:** `ERROR` с "Robot movement failed"

**Решения:**
1. Проверете границите на безопасност на робота
2. Проверете границите на работното пространство
3. Проверете комуникацията с робота
4. Уверете се, че целевите позиции са достижими
5. Проверете за препятствия
6. Проверете калибрирането на робота

---

## Резюме

Модулът за Калибриране на Робот използва **архитектура на машина на състоянията** за извършване на систематично калибриране камера-робот:

1. **Инициализира** системата на камерата
2. **Картографира осите** автоматично (изображение ↔ робот)
3. **Открива шахматна дъска** за установяване на референция и изчисляване на PPM
4. **Открива ArUco маркери** и преобразува в милиметри
5. **Изчислява отмествания** от центъра на изображението
6. **Подравнява робота** към всеки маркер итеративно с адаптивно движение
7. **Измерва височина** на всяка позиция (опционално)
8. **Изчислява хомографска** матрица от съответстващи точки
9. **Валидира и запазва** данни за калибриране

**Ключови Характеристики:**
- Напълно автоматизирано (без ръчна намеса)
- Robust обработка на грешки и логика за повторен опит
- Адаптивно движение за бърза, прецизна конвергенция
- Обратна връзка към UI в реално време чрез message broker
- Проследяване на производителност и анализ на времето
- Декларативни преходи на състояния (валидирани)
- Изчерпателно логване и отстраняване на грешки

**Резултат:** Точна трансформация камера-робот позволяваща прецизни роботни операции управлявани от визия.

---

**Край на Документацията**

