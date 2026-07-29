  function empty() {
    return { onCaseStart: [], onCaseComplete: [] };
  }

  function clone(value) {
    return value ? JSON.parse(JSON.stringify(value)) : empty();
  }

  function actions(draft, field) {
    const value = draft || empty();
    return Array.isArray(value[field]) ? value[field] : [];
  }

  function change(draft, operation) {
    const next = clone(draft);
    operation(next);
    return next;
  }

  function addAction(draft, field, action = 'runCase') {
    return change(draft, (next) => {
      actions(next, field).push({ action, value: '' });
    });
  }

  function updateAction(draft, field, actionIndex, key, value) {
    return change(draft, (next) => {
      actions(next, field)[actionIndex][key] = value;
    });
  }

  function deleteAction(draft, field, actionIndex) {
    return change(draft, (next) => actions(next, field).splice(actionIndex, 1));
  }

  function moveAction(draft, field, actionIndex, delta) {
    return change(draft, (next) => {
      const items = actions(next, field);
      const destination = actionIndex + delta;
      if (destination < 0 || destination >= items.length) return;
      [items[actionIndex], items[destination]] = [items[destination], items[actionIndex]];
    });
  }

  function validationError(draft) {
    for (const field of ['onCaseStart', 'onCaseComplete']) {
      for (const action of actions(draft, field)) {
        if (!['runCase', 'runShell'].includes(action.action)) return 'Lifecycle action type is invalid.';
        if (!String(action.value || '').trim()) return 'Lifecycle action values cannot be empty.';
      }
    }
    return '';
  }

  const LifecycleEditorModel = {
    empty,
    clone,
    actions,
    addAction,
    updateAction,
    deleteAction,
    moveAction,
    validationError,
  };

  export default LifecycleEditorModel;
