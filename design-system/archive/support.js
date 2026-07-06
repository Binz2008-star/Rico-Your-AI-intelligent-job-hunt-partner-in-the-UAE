// Minimal DC runtime stub for archived Motion Lab reference.
// This is not the full DC framework; it provides enough scaffolding
// so the archived HTML file can be opened directly for review.

(function () {
  'use strict';

  // Move <helmet> contents into <head>
  function processHelmets(root) {
    root.querySelectorAll('helmet').forEach(function (helmet) {
      Array.from(helmet.childNodes).forEach(function (node) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          document.head.appendChild(node);
        }
      });
      helmet.remove();
    });
  }

  window.DCLogic = class DCLogic {
    constructor(container) {
      this.container = container;
      this.state = {};
      this._cleanups = [];
    }
    $(s) { return (this.container || document).querySelector(s); }
    $$(s) { return Array.from((this.container || document).querySelectorAll(s)); }
    componentDidMount() {}
    componentDidUpdate() {}
    componentWillUnmount() {}
  };

  class XDcElement extends HTMLElement {
    connectedCallback() {
      processHelmets(this);

      const scripts = this.querySelectorAll('script[type="text/x-dc"][data-dc-script]');
      scripts.forEach(function (script) {
        const code = script.textContent;
        // Execute the script in a scope that exposes DCLogic
        const fn = new Function('DCLogic', code);
        fn(window.DCLogic);

        // The script should define a class named Component
        if (typeof window.Component !== 'function' && typeof Component !== 'undefined') {
          window.Component = Component;
        }

        if (typeof window.Component === 'function') {
          const instance = new window.Component(this);
          instance.componentDidMount();
        }
      });
    }
  }

  if (!customElements.get('x-dc')) {
    customElements.define('x-dc', XDcElement);
  }
})();
