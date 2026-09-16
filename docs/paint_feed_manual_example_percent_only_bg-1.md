# Ръчно изчисляване на максималния paint profile — операторът задава само %

## 1. Основна идея

Операторът **не задава абсолютен feed в mm/s**.

Той задава само:

```text
Paint speed = 0 ... 100%
```

Тук:

```text
100%
```

означава:

> Най-бързата гладка траектория, която конкретният paint contour може да изпълни, без да нарушава effective joint velocity, acceleration и jerk limits.

Стойностите в `mm/s` се изчисляват автоматично от системата и са **резултат**, а не operator input.

---

# 2. Source contour

Да приемем, че след:

```text
OpenCV detection
    ↓
pixel → mm
    ↓
filtering / cleanup
    ↓
interpolation / resampling
```

имаме contour с точки през приблизително 1 mm:

```text
P0 = (0, 0)
P1 = (1, 0)
P2 = (2, 0)
P3 = (3, 0)
P4 = (4, 0)
```

След това contour-ът започва да завива:

```text
P5 = (4.7, 0.7)
P6 = (5.0, 1.7)
P7 = (5.0, 2.7)
```

---

# 3. Какво е `s`

`s` е кумулативното изминато разстояние по **source paint contour-а**.

При 1 mm interpolation приблизително:

```text
P0 -> s = 0 mm
P1 -> s = 1 mm
P2 -> s = 2 mm
P3 -> s = 3 mm
P4 -> s = 4 mm
P5 -> s ≈ 5 mm
P6 -> s ≈ 6 mm
P7 -> s ≈ 7 mm
```

## Променливи

### `s`

Позицията по source paint contour-а.

Единица:

```text
mm
```

### `ds`

Малката стъпка между две последователни source точки.

При равномерна интерполация:

```text
ds ≈ 1 mm
```

---

# 4. RTCP projection и IK

След това:

```text
source contour
    ↓
RTCP projection
    ↓
TCP poses
    ↓
Direct Contour IK
    ↓
joint positions q(s)
```

За всяка sample точка получаваме:

```text
J1
J2
J3
J4
J5
J6
```

---

# 5. Пример на лесна права част

Да приемем, че за `1 mm` source progression IK показва следните joint промени:

```text
J1: dq = +0.005 rad
J2: dq = +0.010 rad
J3: dq = -0.004 rad
J4: dq = +0.015 rad
J5: dq = +0.008 rad
J6: dq = +0.020 rad
```

Тук:

### `q`

Joint position.

Единица:

```text
rad
```

### `dq`

Промяната на joint position между две sample точки:

```text
dq = q_next - q_current
```

Единица:

```text
rad
```

---

# 6. Изчисляваме `dq/ds`

За J6:

```text
dq6 = 0.020 rad
ds  = 1 mm
```

Следователно:

```text
dq6/ds = 0.020 / 1

dq6/ds = 0.020 rad/mm
```

Това означава:

> За всеки 1 mm напредване по source contour-а J6 трябва да се завърти с 0.020 rad.

---

# 7. Как намираме максималния локален feed по velocity

За всеки joint използваме:

```text
Fmax_joint = Vmax_joint / |dq/ds|
```

## Променливи

### `Fmax_joint`

Максималният source feed, който конкретният joint позволява в текущата точка.

Единица:

```text
mm/s
```

### `Vmax_joint`

Максималната допустима velocity на конкретния joint.

Единица:

```text
rad/s
```

### `dq/ds`

Joint movement за 1 mm source contour progression.

Единица:

```text
rad/mm
```

### `|...|`

Абсолютна стойност. Посоката на въртене не влияе на величината на limit-а.

---

# 8. Пример с J6 на права част

Нека effective J6 velocity limit е:

```text
Vmax6 = 15 rad/s
```

Имаме:

```text
dq6/ds = 0.020 rad/mm
```

Тогава:

```text
Fmax6 = 15 / 0.020

Fmax6 = 750 mm/s
```

Важно:

```text
750 mm/s
```

е **изчислен локален максимум само по J6 velocity**.

Операторът не е задал тази стойност.

Друг joint, acceleration, jerk или production margin може да даде много по-нисък реален максимум.

---

# 9. Пример за труден RTCP turn

Да приемем, че при остър RTCP turn за същия `1 mm` source progression J6 се променя:

```text
J6 current = 1.20 rad
J6 next    = 1.50 rad
```

Тогава:

```text
dq6 = 1.50 - 1.20

dq6 = 0.30 rad
```

При:

```text
ds = 1 mm
```

получаваме:

```text
dq6/ds = 0.30 / 1

dq6/ds = 0.30 rad/mm
```

При:

```text
Vmax6 = 15 rad/s
```

максималният локален source feed по J6 velocity е:

```text
Fmax6 = 15 / 0.30

Fmax6 = 50 mm/s
```

Отново:

```text
50 mm/s
```

е **резултат от изчислението**, а не operator input.

---

# 10. Изчисляваме всички joints

За един source interval:

```text
ds = 1 mm
```

нека IK дава:

```text
J1: dq = 0.020 rad
J2: dq = 0.030 rad
J3: dq = 0.010 rad
J4: dq = 0.050 rad
J5: dq = 0.040 rad
J6: dq = 0.300 rad
```

Понеже:

```text
ds = 1 mm
```

имаме:

```text
J1: dq/ds = 0.020 rad/mm
J2: dq/ds = 0.030 rad/mm
J3: dq/ds = 0.010 rad/mm
J4: dq/ds = 0.050 rad/mm
J5: dq/ds = 0.040 rad/mm
J6: dq/ds = 0.300 rad/mm
```

---

# 11. Примерни ZeroErr velocity limits

```text
J1 =  8 rad/s
J2 =  8 rad/s
J3 =  8 rad/s
J4 = 10 rad/s
J5 = 10 rad/s
J6 = 15 rad/s
```

---

# 12. Локален maximum за всеки joint

## J1

```text
Fmax1 = 8 / 0.020
Fmax1 = 400 mm/s
```

## J2

```text
Fmax2 = 8 / 0.030
Fmax2 ≈ 266.7 mm/s
```

## J3

```text
Fmax3 = 8 / 0.010
Fmax3 = 800 mm/s
```

## J4

```text
Fmax4 = 10 / 0.050
Fmax4 = 200 mm/s
```

## J5

```text
Fmax5 = 10 / 0.040
Fmax5 = 250 mm/s
```

## J6

```text
Fmax6 = 15 / 0.300
Fmax6 = 50 mm/s
```

Вземаме най-малката стойност:

```text
Fmax_velocity = min(
    400,
    266.7,
    800,
    200,
    250,
    50
)
```

Резултат:

```text
Fmax_velocity = 50 mm/s
```

Limiting joint:

```text
Joint_6
```

---

# 13. Основната velocity формула

```text
Fmax_velocity(s) = min_j( Vmax_j / |dq_j/ds| )
```

## Променливи

### `Fmax_velocity(s)`

Максималният source feed в позиция `s`, ограничен само от joint velocities.

Единица:

```text
mm/s
```

### `s`

Позицията по source contour-а.

Единица:

```text
mm
```

### `j`

Индекс на joint-а:

```text
J1 ... J6
```

### `Vmax_j`

Effective maximum velocity на joint `j`.

Единица:

```text
rad/s
```

### `dq_j/ds`

Joint movement за 1 mm source progression.

Единица:

```text
rad/mm
```

---

# 14. Защо това още НЕ е operator `100%`

Да приемем, че velocity envelope по contour-а изглежда така:

```text
s =  0 mm  -> 180 mm/s
s = 20 mm  -> 180 mm/s
s = 40 mm  -> 170 mm/s
s = 50 mm  ->  50 mm/s
s = 60 mm  -> 175 mm/s
s = 80 mm  -> 190 mm/s
```

Това са локалните maxima само по velocity.

Robot не може моментално да направи:

```text
180 -> 50 -> 175
```

защото има acceleration и jerk limits.

---

# 15. Acceleration constraint

Joint acceleration зависи от две неща:

1. формата на joint path-а;
2. ускорението/забавянето на source progression.

Използваме:

```text
q_ddot = q_ss * F² + q_s * a_s
```

## Променливи

### `q_ddot`

Joint acceleration.

Единица:

```text
rad/s²
```

### `q_s`

Първата производна на joint position спрямо source distance.

Това е същото като:

```text
dq/ds
```

Единица:

```text
rad/mm
```

### `q_ss`

Втората производна на joint position спрямо source distance.

Показва колко бързо се променя `dq/ds`.

Единица:

```text
rad/mm²
```

### `F`

Текущият source feed, който solver-ът проверява.

Единица:

```text
mm/s
```

### `a_s`

Acceleration на source progression.

Единица:

```text
mm/s²
```

---

# 16. Lookahead

Ако след няколко mm има труден RTCP turn, robot трябва да започне slowdown по-рано.

Velocity envelope може да изглежда като:

```text
180 ──────────────┐
                  │
                  │
                  └── 50
```

Но реалният acceleration-limited profile трябва да е плавен:

```text
180 ───────────╮
               ╲
                ╲
                 ╲
                  50
```

Тоест slowdown започва **преди** ограничената зона.

---

# 17. Jerk и S-curve

Acceleration също не трябва да се променя моментално.

Не искаме:

```text
acceleration:

0 -> -Amax
```

Искаме плавен S-curve transition:

```text
0
 \
  \
   \
    -Amax
```

Jerk е скоростта на изменение на acceleration:

```text
jerk = change_of_acceleration / time
```

За joint trajectory единицата е:

```text
rad/s³
```

---

# 18. Истинското operator `100%`

След като solver-ът приложи:

```text
velocity limits
+
acceleration limits
+
jerk limits
+
lookahead
+
S-curve / jerk-limited retiming
```

получаваме:

```text
F_100(s)
```

`F_100(s)` е:

> Максимално допустимият smooth source-feed profile за конкретния contour.

Това е:

```text
Paint speed = 100%
```

---

# 19. Примерен резултат за `100%`

След пълното изчисление solver-ът може да получи:

```text
source position       F_100(s)

0 mm                    0 mm/s
10 mm                 110 mm/s
20 mm                 165 mm/s
30 mm                 180 mm/s
40 mm                 135 mm/s
50 mm                  42 mm/s
60 mm                 120 mm/s
70 mm                 175 mm/s
80 mm                   0 mm/s
```

Важно:

> Тези `mm/s` стойности са **изчислени от solver-а**.

Операторът не ги задава.

Операторът вижда само:

```text
Paint speed = 100%
```

---

# 20. Какво става при `Paint speed = 70%`

Дефинираме:

```text
p = operator_percent / 100
```

При:

```text
operator_percent = 70
```

имаме:

```text
p = 0.70
```

След това:

```text
F_operator(s) = p * F_100(s)
```

Например, ако solver-ът е изчислил на права зона:

```text
F_100 = 180 mm/s
```

при 70%:

```text
F_70 = 0.70 * 180
F_70 = 126 mm/s
```

Ако в RTCP turn solver-ът е изчислил:

```text
F_100 = 42 mm/s
```

при 70%:

```text
F_70 = 0.70 * 42
F_70 = 29.4 mm/s
```

Отново `mm/s` са internal/result стойности. Operator input остава само `%`.

---

# 21. Time scaling

При operator coefficient `p`:

```text
time_operator = time_100 / p
```

Например:

```text
100% cycle time = 12 s
operator        = 50%
p               = 0.5
```

Тогава:

```text
time_50 = 12 / 0.5

time_50 = 24 s
```

---

# 22. Как се скалират joint dynamics

При чисто time scaling:

```text
velocity_operator     = p * velocity_100
acceleration_operator = p² * acceleration_100
jerk_operator         = p³ * jerk_100
```

При:

```text
p = 0.5
```

получаваме:

```text
velocity     = 50% от 100% profile
acceleration = 25% от 100% profile
jerk         = 12.5% от 100% profile
```

---

# 23. Пример с J6 при operator 50%

Нека при изчисления `100%` profile в дадена точка имаме:

```text
J6 velocity     = 12 rad/s
J6 acceleration = 8 rad/s²
J6 jerk         = 80 rad/s³
```

При:

```text
operator = 50%
p        = 0.5
```

получаваме:

```text
J6 velocity
= 12 * 0.5
= 6 rad/s
```

```text
J6 acceleration
= 8 * 0.5²
= 2 rad/s²
```

```text
J6 jerk
= 80 * 0.5³
= 10 rad/s³
```

---

# 24. Production margin

Operator `100%` не е задължително да използва буквално 100% от physical hardware limits.

Препоръчително е да има production margin.

Пример:

```text
velocity limit scale     = 0.90
acceleration limit scale = 0.85
jerk limit scale         = 0.80
```

Ако physical J6 limits са:

```text
Vmax = 15 rad/s
Amax = 10 rad/s²
Jmax = 100 rad/s³
```

effective production limits стават:

```text
V_effective = 15 * 0.90
V_effective = 13.5 rad/s
```

```text
A_effective = 10 * 0.85
A_effective = 8.5 rad/s²
```

```text
J_effective = 100 * 0.80
J_effective = 80 rad/s³
```

Именно тези effective limits се използват за изчисляването на `F_100(s)`.

---

# 25. Важна подробност при 1 mm interpolation

Source contour може да е интерполиран през:

```text
1 mm
```

но RTCP projection може да раздели един source segment на много projected samples.

Например:

```text
source segment = 1 mm
RTCP turn      = 90°
angular step   = 1°
```

може да даде приблизително:

```text
90 projected samples
```

Тогава:

```text
source_ds_per_projected_sample = 1 / 90
source_ds_per_projected_sample ≈ 0.0111 mm
```

Затова backend-ът не трябва да приема:

```text
ds = 1 mm
```

за всяка IK sample точка.

Той трябва да знае реалния:

```text
source_s_mm
```

или:

```text
source_ds_mm
```

за всяка projected sample.

---

# 26. Защо прави, арки и завои се третират автоматично

Не е нужно да задаваме:

```text
straight = fast
arc      = medium
corner   = slow
```

Solver-ът използва реалното:

```text
dq/ds
```

Ако участъкът е лесен за robot-а:

```text
малък dq/ds
```

той допуска висок `F_100(s)`.

Ако sharp RTCP turn изисква голямо joint движение за малък source progression:

```text
голям dq/ds
```

локалният `F_100(s)` автоматично пада.

---

# 27. Един и същ contour може да има различно `100%`

Същият source contour при различна robot pose може да даде различен joint path `q(s)`.

Например:

```text
Contour A, robot pose 1
100% cycle time = 10 s
```

а:

```text
Contour A, robot pose 2
100% cycle time = 14 s
```

Причината може да бъде:

```text
различен dq/ds
различен limiting joint
различно J6 движение
различна RTCP кинематика
```

Следователно `100%` трябва да се изчислява за конкретната trajectory.

---

# 28. Какво вижда операторът

UI:

```text
PAINT SPEED

[====================] 100%
```

или:

```text
PAINT SPEED

[==============------] 70%
```

Операторът не задава:

```text
mm/s
rad/s
rad/s²
rad/s³
```

---

# 29. Пълният production pipeline

```text
OpenCV contour
    ↓
pixel → mm
    ↓
cleanup / interpolation / offset
    ↓
FINAL SOURCE PAINT CONTOUR
    ↓
source_s
    ↓
RTCP projection
    ↓
projected TCP samples
    ↓
Direct Contour IK
    ↓
q(s)
    ↓
effective joint limits
    ↓
velocity envelope
    ↓
acceleration lookahead
    ↓
jerk-limited S-curve retiming
    ↓
MAXIMUM FEASIBLE PROFILE F_100(s)
    ↓
THIS = OPERATOR 100%
    ↓
operator percentage scaling
    ↓
timed JointTrajectory
    ↓
final dynamic validation
    ↓
collision validation
    ↓
execution
```

---

# 30. Най-важното правило

Операторът задава само:

```text
Paint speed = X%
```

Системата сама изчислява:

```text
F_100(s)
```

за конкретния contour.

`F_100(s)` се получава от:

```text
source contour geometry
+
RTCP projection
+
IK
+
joint velocity limits
+
joint acceleration limits
+
joint jerk limits
+
production margins
```

След това:

```text
F_operator(s) = p * F_100(s)
```

където:

```text
p = operator_percent / 100
```

Пример:

```text
operator = 70%
p        = 0.70
```

тогава:

```text
F_operator(s) = 0.70 * F_100(s)
```

Това е желаната окончателна семантика:

> `%` е operator input; `mm/s`, `rad/s`, `rad/s²` и `rad/s³` са вътрешно изчислени стойности.
