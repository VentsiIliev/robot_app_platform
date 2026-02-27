"""
Unit tests for ApplicationFactory.

These are pure unit tests — all MVC collaborators are mocked, no Qt needed.

Covered:
- build() returns the view
- _create_model() receives the service argument
- _create_controller() receives the model from _create_model and view from _create_view
- controller.load() is called exactly once
- GC fix: view._controller is assigned the controller after build()
- GC fix ordering: load() is called BEFORE view._controller is assigned
- Template method wiring order: create_model → create_view → create_controller → load
"""
import unittest
from unittest.mock import MagicMock

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView


# ── Helpers ────────────────────────────────────────────────────────────────────

class _SimpleView:
    """Minimal stand-in for a view — plain object so attribute assignment is detectable."""
    pass


def _make_factory(model=None, view=None, controller=None):
    """Return a concrete ApplicationFactory wired to the given (or fresh mock) collaborators."""
    _model      = model      or MagicMock(spec=IApplicationModel)
    _view       = view       or MagicMock(spec=IApplicationView)
    _controller = controller or MagicMock(spec=IApplicationController)

    class ConcreteFactory(ApplicationFactory):
        def _create_model(self, service):
            return _model

        def _create_view(self):
            return _view

        def _create_controller(self, m, v):
            return _controller

    return ConcreteFactory(), _model, _view, _controller


# ── Return value ───────────────────────────────────────────────────────────────

class TestBuildReturnValue(unittest.TestCase):

    def test_build_returns_the_view(self):
        factory, _, view, _ = _make_factory()
        result = factory.build(service=MagicMock())
        self.assertIs(result, view)


# ── Template method delegation ─────────────────────────────────────────────────

class TestTemplateMethodDelegation(unittest.TestCase):

    def test_create_model_receives_service_argument(self):
        service = MagicMock()
        received = {}

        model      = MagicMock(spec=IApplicationModel)
        view       = MagicMock(spec=IApplicationView)
        controller = MagicMock(spec=IApplicationController)

        class TrackingFactory(ApplicationFactory):
            def _create_model(self, svc):
                received["service"] = svc
                return model

            def _create_view(self):
                return view

            def _create_controller(self, m, v):
                return controller

        TrackingFactory().build(service)

        self.assertIs(received["service"], service)

    def test_create_controller_receives_model_returned_by_create_model(self):
        model      = MagicMock(spec=IApplicationModel)
        view       = MagicMock(spec=IApplicationView)
        controller = MagicMock(spec=IApplicationController)
        received   = {}

        class TrackingFactory(ApplicationFactory):
            def _create_model(self, svc):
                return model

            def _create_view(self):
                return view

            def _create_controller(self, m, v):
                received["model"] = m
                return controller

        TrackingFactory().build(MagicMock())

        self.assertIs(received["model"], model)

    def test_create_controller_receives_view_returned_by_create_view(self):
        model      = MagicMock(spec=IApplicationModel)
        view       = MagicMock(spec=IApplicationView)
        controller = MagicMock(spec=IApplicationController)
        received   = {}

        class TrackingFactory(ApplicationFactory):
            def _create_model(self, svc):
                return model

            def _create_view(self):
                return view

            def _create_controller(self, m, v):
                received["view"] = v
                return controller

        TrackingFactory().build(MagicMock())

        self.assertIs(received["view"], view)

    def test_controller_load_called_exactly_once(self):
        factory, _, _, controller = _make_factory()
        factory.build(MagicMock())
        controller.load.assert_called_once_with()


# ── GC fix ─────────────────────────────────────────────────────────────────────

class TestGcFix(unittest.TestCase):

    def test_view_controller_attribute_is_set_to_controller(self):
        factory, _, view, controller = _make_factory()
        factory.build(MagicMock())
        self.assertIs(view._controller, controller)

    def test_gc_fix_is_assigned_after_controller_load(self):
        """load() must be called before view._controller is set."""
        model      = MagicMock(spec=IApplicationModel)
        view       = _SimpleView()           # plain object — no auto-attribute magic
        controller = MagicMock(spec=IApplicationController)
        state      = {}

        def check_during_load():
            # At load() time the GC fix must not yet have run
            state["has_controller"] = hasattr(view, "_controller")

        controller.load.side_effect = check_during_load

        class TrackingFactory(ApplicationFactory):
            def _create_model(self, svc):      return model
            def _create_view(self):            return view
            def _create_controller(self, m, v): return controller

        TrackingFactory().build(MagicMock())

        # After build: attribute is present
        self.assertIs(view._controller, controller)
        # During load(): attribute was NOT yet set
        self.assertFalse(state["has_controller"])


# ── Wiring order ───────────────────────────────────────────────────────────────

class TestWiringOrder(unittest.TestCase):

    def test_template_methods_execute_in_correct_order(self):
        call_order = []

        model      = MagicMock(spec=IApplicationModel)
        view       = MagicMock(spec=IApplicationView)
        controller = MagicMock(spec=IApplicationController)

        def tracked_load():
            call_order.append("load")

        controller.load.side_effect = tracked_load

        class OrderedFactory(ApplicationFactory):
            def _create_model(self, svc):
                call_order.append("create_model")
                return model

            def _create_view(self):
                call_order.append("create_view")
                return view

            def _create_controller(self, m, v):
                call_order.append("create_controller")
                return controller

        OrderedFactory().build(MagicMock())

        self.assertEqual(
            call_order,
            ["create_model", "create_view", "create_controller", "load"],
        )


if __name__ == "__main__":
    unittest.main()
