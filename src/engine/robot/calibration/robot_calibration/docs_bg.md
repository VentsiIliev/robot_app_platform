# Модул за калибриране на робот

**Версия:** 7.0  
**Дата:** 10 май 2026  
**Път:** `src/engine/robot/calibration/robot_calibration/`

## Общ преглед

Този модул калибрира връзката между камерата и робота чрез изпълнима машина на състоянията (`ExecutableStateMachine`). Процесът:

1. Проверява, че камерата подава кадри.
2. Автоматично определя как осите на изображението съответстват на осите на робота.
3. Намира референтна дъска и изчислява базов `PPM` (pixels per millimeter).
4. Открива наличните ArUco маркери.
5. Избира подмножество цели за реално изпълнение, като ги разделя на:
   - маркери за fit на хомография
   - маркери за residual/quadratic модел
   - маркери за holdout validation
6. Подравнява робота итеративно към всеки избран маркер.
7. По избор заснема TCP отместване на камерата и/или height map проби.
8. Фитва финалния модел, записва матрицата и допълнителните артефакти.

Това вече не е само “изчисли една хомография от всички маркери”. Текущата реализация поддържа разделено обучение/валидация, fallback към съседни маркери и допълнителни калибрационни артефакти.

## Основни файлове

- `robot_calibration_pipeline.py`  
  Главен оркестратор. Създава `RobotCalibrationContext`, строи state machine-а, стартира процеса и финализира артефактите.
- `RobotCalibrationContext.py`  
  Централно runtime състояние. Държи услуги, target plan, събрани артефакти, прогрес и timing.
- `config_helpers.py`  
  Конфигурации:
  - `RobotCalibrationConfig`
  - `AdaptiveMovementConfig`
  - `RobotCalibrationEventsConfig`
- `CalibrationVision.py`  
  Откриване на chessboard / ChArUco / ArUco, PPM, пикселни точки на маркерите.
- `robot_controller.py`  
  Движение на робота по време на калибрацията.
- `target_planning.py`  
  Избира execution targets и ги partition-ва в `homography_ids`, `residual_ids`, `validation_ids`.
- `ppm_utils.py`  
  Online PPM refinement по време на итеративното подравняване.
- `tcp_offset_capture.py`  
  Събира и финализира `camera_to_tcp_x_offset` и `camera_to_tcp_y_offset`.
- `model_fitting.py`  
  Създава dataset и фитва финалния модел.
- `calibration_report.py`  
  Генерира текстови отчети и JSON артефакти.
- `states/`  
  Отделни handler-и за всяко състояние.

## Контекст и данни

`RobotCalibrationContext` има два слоя:

1. Плоски runtime полета за обратна съвместимост.
2. Групирани изгледи:
   - `services`
   - `target_plan`
   - `artifacts`
   - `progress`
   - `timing`

Най-важните runtime данни са:

- `required_ids`, `candidate_ids`
- `target_plan.target_marker_ids`
- `target_plan.homography_marker_ids`
- `target_plan.residual_marker_ids`
- `target_plan.validation_marker_ids`
- `artifacts.camera_points_for_homography`
- `artifacts.robot_positions_for_calibration`
- `artifacts.available_marker_points_px`
- `artifacts.failed_target_ids`
- `artifacts.skipped_target_ids`
- `camera_tcp_offset_samples`
- `height_map_samples`

## Конфигурация

`RobotCalibrationService` обновява част от настройките непосредствено преди старта чрез `_refresh_runtime_settings()`. Това означава, че документация или UI, които описват конфигурацията, трябва да приемат, че стойностите могат да се презаредят от `settings_service` в последния момент.

Поддържаните ключови настройки включват:

- `required_ids`
- `candidate_ids`
- `min_target_separation_px`
- `homography_target_count`
- `residual_target_count`
- `validation_target_count`
- `auto_skip_known_unreachable_markers`
- `unreachable_marker_failure_threshold`
- `known_unreachable_marker_ids`
- `unreachable_marker_failure_counts`
- `z_target`
- `travel_velocity`, `travel_acceleration`
- `iterative_velocity`, `iterative_acceleration`
- `run_height_measurement`
- `camera_tcp_offset_config`
- `axis_mapping_config`
- `reference_board_mode`
- `charuco_board_width`, `charuco_board_height`
- `charuco_square_size_mm`, `charuco_marker_size_mm`
- `use_marker_centre`
- `use_ransac`

## Машина на състоянията

Текущите състояния са:

```python
INITIALIZING
AXIS_MAPPING
LOOKING_FOR_CHESSBOARD
CHESSBOARD_FOUND
ALIGN_TO_CHESSBOARD_CENTER
LOOKING_FOR_ARUCO_MARKERS
ALL_ARUCO_FOUND
COMPUTE_OFFSETS
ALIGN_ROBOT
ITERATE_ALIGNMENT
CAPTURE_TCP_OFFSET
SAMPLE_HEIGHT
DONE
ERROR
CANCELLED
```

### Реален поток

Нормалният поток е:

```text
INITIALIZING
  -> AXIS_MAPPING
  -> LOOKING_FOR_CHESSBOARD
  -> CHESSBOARD_FOUND
  -> ALIGN_TO_CHESSBOARD_CENTER или директно LOOKING_FOR_ARUCO_MARKERS
  -> ALL_ARUCO_FOUND
  -> COMPUTE_OFFSETS
  -> ALIGN_ROBOT
  -> ITERATE_ALIGNMENT
  -> CAPTURE_TCP_OFFSET (по избор)
  -> SAMPLE_HEIGHT (по избор)
  -> DONE
```

`DONE` не винаги означава “край на целия процес”. Ако има още marker targets, `handle_done_state()` увеличава `current_marker_id` и връща обратно към `ALIGN_ROBOT`. Истинският край е когато последният target е обработен.

### Смисъл на основните състояния

- `INITIALIZING`  
  Чака камерата да започне да подава кадри.
- `AXIS_MAPPING`  
  Определя как движенията по X/Y на робота се виждат в image space.
- `LOOKING_FOR_CHESSBOARD`  
  Търси reference board и изчислява начален `PPM`.
- `CHESSBOARD_FOUND` / `ALIGN_TO_CHESSBOARD_CENTER`  
  Подготвя reference frame преди търсене на ArUco маркери.
- `LOOKING_FOR_ARUCO_MARKERS`  
  Търси наличните маркери и строи началния target plan.
- `ALL_ARUCO_FOUND`  
  Замразява първичните пикселни точки за финалния fit. Това е важно: по-късното итеративно центриране не трябва да презаписва оригиналните correspondences.
- `COMPUTE_OFFSETS`  
  Изчислява началните глобални отмествания на маркерите спрямо image center в калибрационната координатна рамка.
- `ALIGN_ROBOT`  
  Прави първичен robot move към текущия marker.
- `ITERATE_ALIGNMENT`  
  Затворен цикъл за локално донагласяне с online `PPM` refinement, bounded retries и fallback логика.
- `CAPTURE_TCP_OFFSET`  
  По избор върти инструмента и събира проби за `camera_to_tcp` offset.
- `SAMPLE_HEIGHT`  
  По избор събира проби за height map.
- `DONE`  
  Или преминава към следващ marker, или завършва процеса.

## Reference board поведение

Текущият код не е ограничен само до класически chessboard сценарий. `reference_board_mode` може да променя как се държи vision частта, а pipeline-ът подава и ChArUco параметри:

- `charuco_board_width`
- `charuco_board_height`
- `charuco_square_size_mm`
- `charuco_marker_size_mm`

Следователно “LOOKING_FOR_CHESSBOARD” е историческо име на състоянието. На практика то е етапът за установяване на референтната дъска и базовия метричен мащаб.

## Target planning

След като бъдат намерени маркерите, `target_planning.py` изгражда plan с:

- `selected_ids`
- `homography_ids`
- `residual_ids`
- `validation_ids`
- `execution_ids`
- `neighbor_ids`
- `report`

Ключови свойства на текущата логика:

- Предпочитаните `required_ids` се пазят, ако са налични.
- Допълнителни targets се избират така, че да покриват кадъра пространствено.
- Execution order се сортира глобално, за да се намали излишното обикаляне на робота.
- Съседни marker ID-та се запазват за fallback при недостижим или изгубен marker.

## Fallback и недостижими маркери

Това е една от най-големите разлики спрямо по-старото описание.

Текущият код поддържа:

- автоматично пропускане на предварително известни проблемни маркери
- броячи на неуспехите по marker ID
- автоматично повишаване на marker до “known unreachable”
- замяна на провален target със съседен marker

Логиката е в `states/fallback_targets.py`.

При неуспех:

1. неуспешният marker се записва в `failed_target_ids`
2. маркира се и като `skipped_target_ids`
3. текущият target може да бъде заменен с neighbor marker
4. ако има `settings_service`, failure counts и known-unreachable списъкът се persist-ват

## Итеративно подравняване

`ITERATE_ALIGNMENT` е най-сложният етап. Той включва:

- многократни опити за детекция на текущия marker
- median/mean оценка на offset-а
- online `PPM` refinement чрез `ppm_utils.py`
- динамичен брой проби според текущата грешка
- strict post-settle verification
- bounded retries при загубен marker
- fallback към neighbor marker при поредица от неуспехи

Важно:

- началните offsets от `COMPUTE_OFFSETS` остават в глобалната калибрационна рамка
- refined `PPM` се използва само за локалното итеративно донагласяне
- оригиналните camera correspondences за final fit не се заменят с “центрираните” точки

## TCP offset етап

Ако `camera_tcp_offset_config.run_during_robot_calibration == True`, pipeline-ът може да събере проби за TCP offset по време на главната калибрация.

Текущото поведение:

- върти инструмента около `RZ`
- след всяко завъртане отново центрира текущия marker
- пази проби като `CameraTcpOffsetSample`
- накрая усреднява `local_dx`, `local_dy`
- записва:
  - `robot_config.camera_to_tcp_x_offset`
  - `robot_config.camera_to_tcp_y_offset`

Запис става само ако има достатъчно проби и стандартното отклонение е под допустимия праг.

## Height sampling

Ако има `height_measuring_service` и са събрани `height_map_samples`, `handle_done_state()` извиква:

```python
height_measuring_service.save_height_map(context.height_map_samples)
```

Това става при окончателното завършване на всички targets.

## Финализация и артефакти

След успешен край pipeline-ът:

1. строи dataset чрез `build_calibration_dataset()`
2. фитва модела чрез `build_calibration_model()`
3. оценява средната грешка
4. записва хомографската матрица само ако `average_error_mm <= 3`
5. записва JSON артефакти и текстови отчети

### Какво се записва

- `camera_to_robot_matrix_path`  
  `.npy` файл с хомографската матрица
- `<stem>_homography_residual.json`
- `<stem>_model_report.json`

### Какво съдържат отчетите

Отчетите вече сравняват няколко варианта:

- `homography`
- `homography_residual`
- `homography_tps_residual` (ако е активен)

Има и отделни секции за:

- training fit
- holdout validation
- used / skipped / failed marker IDs
- target selection metadata
- known unreachable markers

## Service слой

`RobotCalibrationService` добавя няколко runtime поведения около самия pipeline:

- заключва auto-brightness region, ако камерата го поддържа
- freeze-ва auto brightness adjustment по време на калибрацията
- временно изключва safety walls, ако robot service го поддържа
- възстановява тези настройки във `finally`
- публикува логовете към broker чрез `_BrokerLogHandler`, ако има `events_config`

## Message broker и UI събития

При наличен `RobotCalibrationEventsConfig` се използват:

- `calibration_start_topic`
- `calibration_stop_topic`
- `calibration_image_topic`
- `calibration_log_topic`

Освен това state machine-ът публикува промени на състоянието в topic:

```text
ROBOT_CALIBRATION_STATE
```

## Ограничения и важни бележки

- `LOOKING_FOR_CHESSBOARD` е legacy име; поведението вече покрива и reference-board сценарии извън чист chessboard-only flow.
- Състоянието `CANCELLED` съществува и е използвано реално при stop request.
- Не всеки намерен маркер се използва за финалния fit.
- Не всеки използван маркер участва в една и съща роля; има отделни training / residual / validation групи.
- Хомографията не се записва автоматично при висока средна грешка.
- TCP offset и height map етапите са опционални.

## Практическо резюме

Ако трябва да се разбере модулът бързо, четете в този ред:

1. `robot_calibration_pipeline.py`
2. `RobotCalibrationContext.py`
3. `states/robot_calibration_states.py`
4. `states/looking_for_aruco_markers_handler.py`
5. `states/iterate_alignment.py`
6. `target_planning.py`
7. `model_fitting.py`
8. `tcp_offset_capture.py`

Това е актуалният модел на работа към 10 май 2026: state-machine pipeline с target partitioning, fallback targets, online PPM refinement и разширена финализация с допълнителни артефакти.
