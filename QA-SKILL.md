---
name: anti-pattern-testing
description: >
  Enforce meaningful, non-fake test quality when writing, reviewing, or generating
  tests in any language or framework. Use this skill whenever the user says "write
  tests", "add unit tests", "review my tests", "improve test coverage", "check if
  my tests are good", or pastes test code for feedback. Also trigger when generating
  tests as part of a broader coding task — do not wait to be asked explicitly. This
  skill catches fake, tautological, over-mocked, and non-validating tests before
  they reach the codebase.
---

# Anti-Pattern Testing Skill

## Purpose

Prevent the most common class of test quality failure: tests that pass even when
the implementation is broken. Every test produced or reviewed under this skill must
satisfy a hard validation gate before being considered complete.

---

## Hard Gate: The Falsifiability Check

**Before finalizing any test, you MUST answer:**

> "If the implementation were incorrect, would this test fail?"

- If **yes** → the test is valid. Proceed.
- If **no** or **not reliably** → the test is invalid. Rewrite it.

This is not optional reflection. It is a blocking step. Do not present a test suite
to the user until every test has passed this gate.

---

## Required Output Format

For every test written or reviewed, produce this annotation (inline comment or
accompanying table):

```
Test: <test name>
Precondition: <setup / inputs>
Action: <function/method under test>
Assert: <specific value, state, or side effect>
Bug caught: <what breaks in the implementation if this assertion fails>
```

If you cannot fill in **Bug caught** with a concrete answer, the test must be rewritten.

---

## Anti-Pattern Checklist

Run this checklist per test. If any box is unchecked, rewrite before proceeding.

```
[ ] Asserts a specific value, not just existence or truthiness
[ ] Would fail if the function returned a wrong-but-truthy result
[ ] Would fail if the function returned early / did nothing
[ ] Mock surface area is minimized — real logic is actually executed
[ ] Covers at least one error path or edge case (not only the happy path)
[ ] Does not repeat the implementation logic inside the assertion
[ ] Checks observable outputs or side effects, not internal/private state
```

---

## Anti-Pattern Catalog with Examples

### 1. No Meaningful Assertion (Crash-Only Test)

```python
# BAD — only proves the function doesn't throw
def test_parse_config():
    result = parse_config("config.yaml")
    assert result is not None

# GOOD — proves specific values are correct
def test_parse_config():
    result = parse_config("config.yaml")
    assert result["timeout"] == 30
    assert result["retries"] == 3
    assert result["host"] == "localhost"
# Bug caught: wrong default values, missing keys, silent parse failures
```

---

### 2. Tautological Assertion (Implementation Repeated in Test)

```python
# BAD — test mirrors the implementation; always passes even if logic is wrong
def test_discount():
    price = 100
    discount = price * 0.1   # same formula as the implementation
    assert apply_discount(price) == price - discount

# GOOD — hardcoded expected value derived independently
def test_discount():
    assert apply_discount(100) == 90.0
    assert apply_discount(0) == 0.0
    assert apply_discount(200) == 180.0
# Bug caught: wrong discount rate, off-by-one, missing rounding
```

---

### 3. Everything Mocked (No Real Logic Executed)

```python
# BAD — mocking the thing under test; nothing real runs
@patch("myapp.calculator.add")
def test_sum(mock_add):
    mock_add.return_value = 5
    assert calculate_sum(2, 3) == 5  # trivially true

# GOOD — mock only external I/O, test real logic
def test_sum():
    assert calculate_sum(2, 3) == 5
    assert calculate_sum(-1, 1) == 0
    assert calculate_sum(0, 0) == 0
# Bug caught: wrong operator, integer overflow, sign errors
```

---

### 4. Overly Broad Assertion

```python
# BAD — status 200 says nothing about correctness
def test_create_user(client):
    response = client.post("/users", json={"name": "Alice"})
    assert response.status_code == 200

# GOOD — validate the response body and side effects
def test_create_user(client, db):
    response = client.post("/users", json={"name": "Alice"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alice"
    assert "id" in body
    assert db.query(User).filter_by(name="Alice").count() == 1
# Bug caught: wrong status code, missing fields, user not persisted
```

---

### 5. Only Checking Call, Not Result

```python
# BAD — proves the function was called, not that it did the right thing
def test_sends_email(mock_send):
    notify_user(user_id=42, message="Hello")
    mock_send.assert_called_once()

# GOOD — assert on the arguments and outcome
def test_sends_email(mock_send):
    notify_user(user_id=42, message="Hello")
    mock_send.assert_called_once_with(
        to="user42@example.com",
        subject="Notification",
        body="Hello"
    )
# Bug caught: wrong recipient, wrong subject, message not passed through
```

---

### 6. Hardcoded Always-Pass Expectation

```javascript
// BAD — expected value chosen to match whatever the function returns
test("formats date", () => {
  const result = formatDate(new Date("2024-01-15"));
  expect(result).toBeTruthy();  // any string passes
});

// GOOD — assert the exact formatted string
test("formats date", () => {
  expect(formatDate(new Date("2024-01-15"))).toBe("15 Jan 2024");
  expect(formatDate(new Date("2000-12-31"))).toBe("31 Dec 2000");
});
// Bug caught: wrong format, missing zero-padding, wrong month name
```

---

### 7. Snapshot Without Critical Field Validation

```javascript
// BAD — snapshot will pass even if critical fields change silently
it("renders user card", () => {
  const { container } = render(<UserCard user={mockUser} />);
  expect(container).toMatchSnapshot();
});

// GOOD — assert on critical rendered content
it("renders user card", () => {
  const { getByText, getByRole } = render(<UserCard user={mockUser} />);
  expect(getByText("Alice")).toBeInTheDocument();
  expect(getByRole("img")).toHaveAttribute("alt", "Alice's avatar");
  expect(getByText("alice@example.com")).toBeInTheDocument();
});
// Bug caught: name not rendered, broken avatar, email missing
```

---

### 8. Missing Error Path Coverage

```python
# INCOMPLETE — only tests success; no error paths
def test_divide():
    assert divide(10, 2) == 5.0

# COMPLETE — includes error and edge cases
def test_divide():
    assert divide(10, 2) == 5.0
    assert divide(0, 5) == 0.0
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
    with pytest.raises(TypeError):
        divide("10", 2)
# Bug caught: missing zero-guard, silent type coercion, wrong exception type
```

---

## Mocking Rules: What Is and Is Not Allowed

### The Core Principle

Mock **infrastructure**, not **logic**. A mock replaces something that is slow,
non-deterministic, or outside your control. It must never replace the behavior
you are trying to verify.

---

### ✅ Allowed to Mock

| Category | Examples | Reason |
|---|---|---|
| **Network / HTTP** | REST APIs, third-party services, webhooks | Slow, external, non-deterministic |
| **Databases** | SQL queries, ORM calls, Redis | Side effects, requires real infra |
| **File system** | `open()`, `os.path`, disk reads/writes | Environment-dependent |
| **Time / clocks** | `datetime.now()`, `Date.now()`, `time.sleep()` | Non-deterministic |
| **Random / UUID** | `random()`, `uuid4()` | Non-deterministic |
| **Email / SMS / push** | SMTP, Twilio, Firebase | External side effects |
| **Hardware / sensors** | Serial ports, cameras, GPIO | Requires physical device |
| **Environment / config** | `os.environ`, secrets, feature flags | Environment-dependent |
| **Heavy slow dependencies** | ML model inference, video encoding | Impractically slow in unit tests |

**Rule:** After mocking, assert on what your code *did with* the mock — the
arguments passed, the number of calls, and their order.

---

### ❌ Not Allowed to Mock

| Category | Examples | Why It's Forbidden |
|---|---|---|
| **The unit under test** | Mocking the function you're testing | Nothing real executes |
| **Core business logic** | Calculation, validation, transformation rules | Removes the thing being verified |
| **Data structures you own** | Your own models, DTOs, value objects | Use real instances |
| **Pure functions** | Anything with no side effects | No reason to mock; just call it |
| **Simple helpers** | String formatters, math utils, converters | Mocking adds cost, no benefit |
| **Interfaces you own** | Internal service interfaces (Go, C#, Java) | Use a real implementation or fake |
| **Logging / metrics** | `logger.info()`, Prometheus counters | Unless asserting on log output specifically |

**Rule:** If you mock something from this list, stop and ask: "Am I trying to
avoid testing the thing I'm supposed to be testing?" If yes, restructure the
test or the design.

---

### The Fake vs Mock Distinction

Prefer **fakes** over **mocks** when the dependency has real behavior worth preserving.

| Type | Description | When to Use |
|---|---|---|
| **Mock** | Records calls, returns configured values, no logic | Verifying interactions (e.g., email sent) |
| **Stub** | Returns fixed data, no assertions | Providing controlled input |
| **Fake** | Lightweight real implementation (e.g., in-memory DB) | When behavior matters, not just calls |
| **Spy** | Real object that also records calls | When you need both real behavior + call verification |

```python
# Mock — use when you need to verify the call happened correctly
mock_email.assert_called_once_with(to="user@example.com", subject="Welcome")

# Fake — use when real behavior matters (e.g., query results affect logic)
class FakeUserRepository:
    def __init__(self): self._store = {}
    def save(self, user): self._store[user.id] = user
    def find(self, id): return self._store.get(id)

# Use the fake in tests — real logic, no database
repo = FakeUserRepository()
service = UserService(repo)
service.register("Alice")
assert repo.find(1).name == "Alice"
```

---

### Over-Mocking Warning Signs

Flag a test for review if it:
- Has more mock setup lines than assertion lines
- Mocks 3 or more collaborators in a single unit test
- Requires `return_value.return_value.return_value` chaining
- Would still pass if the function body were completely emptied
- Cannot be understood without reading the mock setup first

When you see these signs, the test likely needs redesign — either extract the
logic into a pure function (easier to test without mocks) or write an integration
test instead.

---

### Integration vs Unit: When to Drop Mocks Entirely

Some behavior is only meaningful at the integration level. Write a real
integration test (no mocks, real dependencies) when:

- The correctness depends on how two components interact
- You are testing database query behavior, transaction boundaries, or ORM mappings
- You are testing HTTP middleware, auth flows, or request pipelines
- A bug in the interaction between real components has burned you before

Mark integration tests clearly and keep them in a separate suite so they don't
slow down unit test runs.

---

## Language-Specific Pitfalls

### Python (pytest / unittest)
- Avoid `assert result` — use `assert result == expected_value`
- Avoid `mock.assert_called()` alone — use `assert_called_once_with(...)`
- Use `pytest.raises(ExactException)` not bare `try/except`

### JavaScript / TypeScript (Jest / Vitest)
- Avoid `expect(x).toBeTruthy()` — use `expect(x).toBe(exactValue)`
- Don't over-rely on snapshots; combine with explicit field assertions
- When mocking fetch/axios, assert on request payload, not just that it was called

### Go
- Use `t.Errorf` with the actual vs expected values printed
- Prefer table-driven tests to cover multiple cases systematically
- Don't mock interfaces you own — use real implementations in tests

### C# (xUnit / NUnit)
- Use `Assert.Equal(expected, actual)` — order matters for error messages
- Avoid `Assert.NotNull` alone — follow with type-specific assertions
- Use `Assert.Throws<T>` not try/catch in tests

---

## Strengthening Rules Summary

| Weak Pattern | Strong Replacement |
|---|---|
| `assert result` | `assert result == 42` |
| `assert result is not None` | `assert result["key"] == "value"` |
| `mock.assert_called()` | `mock.assert_called_once_with(arg1, arg2)` |
| `status == 200` | `status == 201` + body field checks |
| `toBeTruthy()` | `toBe("exact string")` |
| Snapshot only | Snapshot + critical field assertions |
| Happy path only | Happy path + error path + boundary values |

---

## Minimum Coverage Requirements

Every tested unit should have:
1. **At least one happy path** with exact value assertions
2. **At least one error/exception path**
3. **At least one boundary/edge case** (zero, empty, max, null)

If a test suite covers only case 1, flag it as incomplete and add cases 2 and 3.

---

## Integration Test Addendum

### When to Write Integration Tests vs Unit Tests

Use this decision table before choosing a test type:

| Question | Unit Test | Integration Test |
|---|---|---|
| Does correctness depend on a single function's logic? | ✅ | — |
| Does correctness depend on two or more components interacting? | — | ✅ |
| Does it involve a real database query, ORM mapping, or transaction? | — | ✅ |
| Does it test an HTTP endpoint end-to-end (routing + auth + handler + DB)? | — | ✅ |
| Does it verify a queue consumer processes a message correctly? | — | ✅ |
| Can all dependencies be replaced with fakes without losing meaning? | ✅ | — |
| Has a bug in component interaction burned you before? | — | ✅ |
| Does it need to run in under 10ms? | ✅ | — |

**Rule of thumb:** if you find yourself writing a unit test with 4+ mocks to
simulate a real interaction, stop — write an integration test instead.

---

### How to Structure Integration Test Suites

#### Directory Layout (pytest)

```
tests/
├── unit/                   # Fast, no I/O, all mocked externals
│   ├── test_discount.py
│   └── test_parser.py
├── integration/            # Real DB, real HTTP, real queues
│   ├── conftest.py         # Shared fixtures: DB session, test client, etc.
│   ├── test_user_api.py
│   ├── test_order_flow.py
│   └── db/
│       └── test_repository.py
└── e2e/                    # Full stack, runs against deployed env (optional)
    └── test_checkout.py
```

#### pytest Markers

Mark integration tests explicitly so they can be run separately:

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests that require real infrastructure",
    "slow: marks tests that take more than 1 second",
]

# Run only unit tests (fast, default in CI pre-merge)
# pytest -m "not integration"

# Run integration tests (in CI post-merge or nightly)
# pytest -m integration
```

#### conftest.py: Shared Fixtures

```python
# tests/integration/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from myapp.database import Base
from myapp.main import create_app

@pytest.fixture(scope="session")
def engine():
    # Use a real test database — never the production DB
    engine = create_engine("postgresql://localhost/myapp_test")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def db_session(engine):
    # Each test gets a fresh transaction, rolled back after
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    app = create_app(db=db_session)
    with app.test_client() as c:
        yield c
```

**Key patterns:**
- `scope="session"` for expensive setup (DB schema creation)
- `scope="function"` + rollback for test isolation — no state leaks between tests
- Never share mutable state between tests through module-level variables

---

### Database Test Patterns

#### ✅ Test the Real Query, Not the ORM Call

```python
# BAD — mocks the repository; proves nothing about the query
def test_find_active_users(mock_repo):
    mock_repo.find_active.return_value = [User(name="Alice")]
    result = UserService(mock_repo).get_active_users()
    assert len(result) == 1

# GOOD — real DB, real query, real result
@pytest.mark.integration
def test_find_active_users(db_session):
    db_session.add_all([
        User(name="Alice", active=True),
        User(name="Bob",   active=False),
        User(name="Carol", active=True),
    ])
    db_session.flush()

    repo = UserRepository(db_session)
    result = repo.find_active()

    assert len(result) == 2
    assert {u.name for u in result} == {"Alice", "Carol"}
# Bug caught: wrong filter condition, missing index hint, ORM mapping error
```

#### ✅ Test Transaction Boundaries

```python
@pytest.mark.integration
def test_transfer_rolls_back_on_failure(db_session):
    alice = Account(owner="Alice", balance=100)
    bob   = Account(owner="Bob",   balance=0)
    db_session.add_all([alice, bob])
    db_session.flush()

    with pytest.raises(InsufficientFundsError):
        transfer(db_session, from_id=bob.id, to_id=alice.id, amount=50)

    db_session.refresh(alice)
    db_session.refresh(bob)
    assert alice.balance == 100  # unchanged
    assert bob.balance == 0      # unchanged
# Bug caught: partial commit, missing rollback, wrong account debited
```

---

### API / HTTP Test Patterns

#### ✅ Test the Full Request Pipeline

```python
@pytest.mark.integration
def test_create_user_returns_created(client, db_session):
    response = client.post("/api/users", json={"name": "Alice", "email": "alice@example.com"})

    # Assert HTTP contract
    assert response.status_code == 201
    body = response.get_json()
    assert body["name"] == "Alice"
    assert body["email"] == "alice@example.com"
    assert isinstance(body["id"], int)

    # Assert persistence — the DB was actually written
    user = db_session.query(User).filter_by(email="alice@example.com").first()
    assert user is not None
    assert user.name == "Alice"
# Bug caught: handler returns 200 instead of 201, user not saved, wrong field name
```

#### ✅ Test Auth and Permission Boundaries

```python
@pytest.mark.integration
def test_unauthorized_request_rejected(client):
    response = client.get("/api/admin/users")  # no auth header
    assert response.status_code == 401

@pytest.mark.integration
def test_forbidden_for_non_admin(client, regular_user_token):
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {regular_user_token}"}
    )
    assert response.status_code == 403
# Bug caught: missing auth middleware, wrong role check, silent permission bypass
```

#### ✅ Test Validation and Error Responses

```python
@pytest.mark.integration
def test_missing_required_field_returns_422(client):
    response = client.post("/api/users", json={"name": "Alice"})  # email missing
    assert response.status_code == 422
    body = response.get_json()
    assert "email" in body["detail"][0]["loc"]
# Bug caught: missing input validation, wrong error format, wrong status code
```

---

### Integration Test Anti-Patterns

#### ❌ Sharing State Between Tests

```python
# BAD — test order matters; second test depends on first test's data
def test_create_order():
    order = Order.objects.create(product="Widget", qty=1)
    assert order.id is not None

def test_order_count():
    assert Order.objects.count() == 1  # fails if test_create_order didn't run first
```

```python
# GOOD — each test creates its own data; order is irrelevant
@pytest.fixture
def order(db_session):
    o = Order(product="Widget", qty=1)
    db_session.add(o)
    db_session.flush()
    return o

def test_order_count(db_session, order):
    assert db_session.query(Order).count() == 1
```

---

#### ❌ Hitting Real External Services

```python
# BAD — calls real Stripe API in a test; slow, costly, non-deterministic
def test_charge_customer():
    result = stripe.charge(customer_id="cus_real123", amount=5000)
    assert result["status"] == "succeeded"
```

```python
# GOOD — use responses library or a sandbox/test-mode URL
import responses

@responses.activate
def test_charge_customer():
    responses.post(
        "https://api.stripe.com/v1/charges",
        json={"id": "ch_test", "status": "succeeded"},
        status=200,
    )
    result = charge_customer(customer_id="cus_test123", amount=5000)
    assert result.status == "succeeded"
    assert result.charge_id == "ch_test"
# Bug caught: wrong API payload, missing field mapping, error not handled
```

---

#### ❌ Testing Implementation Details Instead of Outcomes

```python
# BAD — asserts on SQL query string; breaks on any refactor
def test_user_query(db_session, caplog):
    get_active_users(db_session)
    assert "WHERE active = true" in caplog.text

# GOOD — assert on the outcome, not the query internals
def test_user_query(db_session):
    db_session.add_all([User(active=True), User(active=False)])
    db_session.flush()
    result = get_active_users(db_session)
    assert len(result) == 1
    assert result[0].active is True
```

---

#### ❌ No Cleanup / Leaking State to Other Tests

```python
# BAD — uploads a real file, never deletes it; pollutes the filesystem
def test_upload_avatar(client):
    response = client.post("/upload", data={"file": open("avatar.png", "rb")})
    assert response.status_code == 200

# GOOD — use tmp_path fixture and clean up explicitly
def test_upload_avatar(client, tmp_path):
    fake_file = tmp_path / "avatar.png"
    fake_file.write_bytes(b"fakepngdata")
    response = client.post("/upload", data={"file": fake_file.open("rb")})
    assert response.status_code == 200
    assert response.get_json()["filename"] == "avatar.png"
    # tmp_path is automatically cleaned up by pytest
```

---

### Integration Test Checklist

Run this before marking an integration test complete:

```
[ ] Uses a dedicated test database / environment, never production
[ ] Test is isolated — no shared mutable state with other tests
[ ] DB changes are rolled back or the schema is reset after each test
[ ] External paid/stateful APIs are stubbed (responses, httpretty, VCR)
[ ] Asserts on both the HTTP response AND the persisted DB state
[ ] Covers at least one failure/rejection path (bad input, missing auth)
[ ] Marked with @pytest.mark.integration so it can be run separately
[ ] Does not depend on test execution order
```

---

## Robot App Platform Addendum

This repository is not a generic web/backend codebase. It has a layered architecture,
robot-system workflows, geometry-heavy logic, Qt applications, and hardware-facing
services. The rules above still apply, but the following repo-specific rules are mandatory.

### 1. Do Not Count Metadata Smoke Tests as Real Coverage

The following do **not** count as meaningful protection by themselves:

- `ApplicationSpec` exists
- `folder_id` / `icon` / `name` matches
- factory returns `WidgetApplication`
- object implements an interface
- constructor does not raise
- function returns `list` / `tuple` / `bool`

These are acceptable only as tiny smoke checks. They must not be presented as
real integration or behavior coverage.

### 2. Commented-Out or Undiscovered Tests Count as Zero

If a file is:

- fully commented out
- outside the main test harness
- not discovered by `python tests/run_tests.py`

then it provides **zero** protection and must be treated as absent.

Examples of this failure mode in this repo include:

- commented-out suites that look substantial but never run
- ad hoc `*_test.py` files living under `src/`

### 3. For Robot Process Tests, Assert Outcomes, Not Just Calls

For workflows, processes, and coordinators, do not stop at:

- collaborator called
- state method invoked
- topic published once

Also assert:

- final process state
- error code / stage when failing
- emitted payload contents when events matter
- critical computed poses or plan values
- stop/pause/resume behavior under interruption

A process test is weak if it would still pass after replacing most of the body
with mocked call-throughs.

### 4. For Geometry / Vision / Alignment Code, Prefer Numeric Truth Over Mock Assertions

When testing:

- path planning
- transforms
- contour alignment
- homography
- pickup / placement pose generation

prefer assertions like:

- exact coordinates
- tolerance-based numeric comparisons
- invariant preservation
- error bounds
- point-count / ordering guarantees where relevant

Avoid reducing these tests to:

- “helper was called”
- “method returned a tuple”
- “result is not None”

### 5. Mock at the Hardware Boundary, Keep Core Logic Real

In this repo, allowed mock boundaries usually include:

- robot drivers
- ROS bridge clients
- camera capture services
- Modbus / serial transports
- HTTP transports
- vacuum / generator / laser hardware adapters
- filesystem and time

Inside those boundaries:

- keep motion/planning/process logic real
- keep geometry/math logic real
- keep payload mapping/transformation logic real

If the test mocks both the hardware boundary and the decision-making logic, it
is probably not testing anything important.

### 6. Prefer Fakes and Spies Over Deep Mock Chains

For this codebase, fakes are often better than large mock setups for:

- repositories
- settings services
- workpiece catalogs
- capture snapshots
- message recording
- in-memory process inputs

Use spies when you need both:

- real behavior
- verification of calls or published events

If a test requires `return_value.return_value.return_value`, stop and redesign it.

### 7. Plugin / Factory Tests Must Validate Real Wiring

A useful factory or plugin test should go beyond top-level type checks.

Prefer verifying:

- the expected concrete service is injected
- controller/view/model are wired together correctly
- at least one meaningful user action or load path works
- cleanup/unsubscribe behavior works where applicable

Weak pattern:

- “factory returns WidgetApplication”

Stronger pattern:

- build widget
- register messaging if needed
- create widget
- assert controller/service wiring
- trigger one real behavior through the public boundary

### 8. Internal State Checks Are Allowed When They Protect Wiring

The generic rule says to prefer observable outputs over private state. That still holds.
But in this repo, narrowly scoped internal-state assertions are acceptable when they
protect framework wiring that users rely on, for example:

- `view._controller` retention
- stored subscriptions/spies
- process sequence assembly
- cached workpiece or settings state after a public action

This is allowed only when:

- the state is a real part of the framework contract
- asserting only public surface behavior would miss the regression

Do not use this as a license to test arbitrary internals.

### 9. Characterization Tests Come Before Refactors

Before refactoring a messy module, first lock down:

- current externally visible behavior
- current failure behavior
- event publication behavior
- numeric outputs and invariants

This is especially important for:

- `src/robot_systems/paint/`
- `src/engine/core/`
- `src/engine/vision/`
- shared geometry/process code

The first goal is not beauty. The first goal is preventing accidental behavior drift.

### 10. Minimum Expectations by Module Type

#### Application service / controller

Must cover:

- happy path
- failure path
- one meaningful state/UI update path
- unsubscribe/cleanup path if broker usage exists

#### Process / workflow

Must cover:

- success path
- stop/cancel path
- at least one hardware/service failure path
- emitted state/error/event correctness

#### Geometry / alignment / planning

Must cover:

- nominal numeric case
- edge/degenerate input
- tolerance-based expected output
- one invariant/property assertion

#### Repository / settings mapper

Must cover:

- round-trip serialization
- missing/default field behavior
- malformed input handling where relevant

### 11. Specific Weak Patterns to Flag in This Repo

Flag these immediately during review:

- `assertTrue(callable(...))`
- `assertIsInstance(result, tuple)` without semantic assertions
- `assertEqual(len(result), N)` as the main proof of correctness
- `assertTrue(ok)` without checking returned data or state
- “delegates to dependency” as the only behavior test
- source-code string inspection used as architecture proof
- plugin tests that validate only spec metadata

### 12. Preferred Commands and Harness Truth

For this repository, the authoritative suite is the one run by:

```bash
python tests/run_tests.py
```

If a test is not part of that path, say so explicitly. Do not imply that repo
confidence includes side-test scripts or dormant files.
