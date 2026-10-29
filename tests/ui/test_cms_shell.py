import json

import pytest

from tests.ui.helpers import capture_page, open_page


pytestmark = pytest.mark.ui
CASES = [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)]
ROUTES = ['/equipment-status2', '/dashboard_ui6', '/history2', '/main_ct', '/dashboard2?dataset=1']


def shell_geometry(page):
    return page.evaluate('''() => {
      const sidebar = document.querySelector('#cms-sidebar').getBoundingClientRect();
      const main = document.querySelector('main').getBoundingClientRect();
      const content = document.querySelector('main');
      const style = getComputedStyle(content);
      const header = document.querySelector('.top, .workspace-header, .history-heading, .topbar');
      const headerRect = header.getBoundingClientRect();
      const anchor = content.querySelector('.js-plotly-plot, table, .equipment-status-list, .cms-chart-card, .workspace-panel');
      const anchorRect = anchor?.getBoundingClientRect();
      return {nav: sidebar.width, width: main.width, x: main.x, y: main.y,
        padding: [style.paddingTop, style.paddingRight, style.paddingBottom, style.paddingLeft],
        headerHeight: headerRect.height, headerY: headerRect.y,
        rootWidth: document.documentElement.scrollWidth, viewport: innerWidth,
        anchor: anchorRect ? {width: anchorRect.width, x: anchorRect.x, y: anchorRect.y} : null};
    }''')


@pytest.mark.parametrize('cms_desktop_case', CASES, indirect=True)
@pytest.mark.parametrize('path', ROUTES)
def test_hover_and_focus_do_not_resize_content(cms_page, cms_desktop_case, path):
    open_page(cms_page, path)
    if path.startswith('/dashboard2'):
        cms_page.wait_for_function("document.querySelector('#trend-chart')?.data?.length > 0")
    sidebar = cms_page.locator('#cms-sidebar')
    toggle = cms_page.locator('#cms-sidebar-toggle')
    assert sidebar.count() == 1
    assert toggle.get_attribute('aria-expanded') == 'true'
    active = {'/equipment-status2': '/equipment-status2', '/dashboard_ui6': '/dashboard_ui6',
          '/history2': '/history2', '/main_ct': '/main_ct', '/dashboard2?dataset=1': '/equipment-status2'}
    assert cms_page.locator('#cms-sidebar [aria-current="page"]').get_attribute('href') == active[path]
    evidence = []
    for expanded, width in [(True, 244), (False, 76)]:
        if not expanded:
            toggle.click()
        cms_page.mouse.move(900, 100)
        before = shell_geometry(cms_page)
        assert before['nav'] == width
        assert before['padding'] == ['32px', '38px', '48px', '38px']
        assert abs(before['headerHeight'] - 60) <= 1
        sidebar.hover()
        after_hover = shell_geometry(cms_page)
        toggle.focus()
        cms_page.keyboard.press('Tab')
        assert cms_page.locator('#cms-sidebar nav a').first.evaluate('node => node === document.activeElement')
        after_tab = shell_geometry(cms_page)
        for after in (after_hover, after_tab):
            assert abs(after['width'] - before['width']) <= 1
            assert abs(after['x'] - before['x']) <= 1
            assert after['nav'] == width
            assert before['anchor'] and after['anchor']
            for dimension in ('width', 'x', 'y'):
              assert abs(after['anchor'][dimension] - before['anchor'][dimension]) <= 1
        overflow = cms_page.evaluate('''() => [...document.querySelectorAll('main *')]
          .filter(node => node.getBoundingClientRect().right > innerWidth + 1)
          .slice(0, 15).map(node => ({tag: node.tagName, class: node.className,
            width: node.getBoundingClientRect().width, right: node.getBoundingClientRect().right}))''')
        assert before['rootWidth'] <= before['viewport'] + 1, overflow
        target = capture_page(cms_page, 'task3-shell-' + path.split('?')[0].strip('/') + ('-expanded' if expanded else '-collapsed'))
        evidence.append({'before': before, 'hover': after_hover, 'tab': after_tab})
        target.with_suffix('.shell.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


def test_sidebar_keyboard_and_persistence(cms_page):
    open_page(cms_page, '/equipment-status2')
    toggle = cms_page.locator('#cms-sidebar-toggle')
    assert toggle.get_attribute('aria-controls') == 'cms-sidebar'
    assert toggle.get_attribute('aria-expanded') == 'true'
    assert toggle.get_attribute('aria-label')
    cms_page.evaluate('''async () => {
      window.shellEvents = [];
      document.addEventListener('cms:layout-change', event => shellEvents.push(event.detail));
      const shell = await import('/static/modules/core/cms-operations.js?v=task3');
      shell.initCmsShell(); shell.initCmsShell();
      shell.setSidebarExpanded(true);
    }''')
    assert cms_page.evaluate('shellEvents.length') == 0
    toggle.click()
    assert toggle.get_attribute('aria-expanded') == 'false'
    assert cms_page.evaluate('document.body.dataset.cmsNav') == 'collapsed'
    assert cms_page.evaluate("localStorage.getItem('cms.sidebar.expanded')") == 'false'
    toggle.press('Enter')
    assert toggle.get_attribute('aria-expanded') == 'true'
    toggle.press('Space')
    assert toggle.get_attribute('aria-expanded') == 'false'
    assert toggle.evaluate('node => node === document.activeElement')
    assert cms_page.evaluate('shellEvents.length') == 3
    cms_page.evaluate('''async () => {
      const shell = await import('/static/modules/core/cms-operations.js?v=task3');
      shell.setSidebarExpanded(false);
    }''')
    assert cms_page.evaluate('shellEvents.length') == 3
    cms_page.locator('#cms-sidebar a[href="/history2"]').click()
    cms_page.wait_for_load_state('networkidle')
    assert cms_page.locator('#cms-sidebar-toggle').get_attribute('aria-expanded') == 'false'
    assert cms_page.locator('#cms-sidebar [aria-current="page"]').get_attribute('href') == '/history2'
    cms_page.reload(wait_until='networkidle')
    assert cms_page.locator('#cms-sidebar-toggle').get_attribute('aria-expanded') == 'false'
    cms_page.locator('#cms-sidebar-toggle').press('Enter')
    assert cms_page.locator('#cms-sidebar-toggle').get_attribute('aria-expanded') == 'true'
    open_page(cms_page, '/dashboard2?dataset=1')
    assert cms_page.locator('#cms-sidebar-toggle').get_attribute('aria-expanded') == 'true'
    assert cms_page.locator('#cms-sidebar [aria-current="page"]').get_attribute('href') == '/equipment-status2'


@pytest.mark.parametrize('failure', ['getItem', 'setItem', 'getter', 'invalid'])
def test_storage_failure_is_nonblocking(cms_page, failure):
    errors = []
    cms_page.on('pageerror', lambda error: errors.append(str(error)))
    cms_page.add_init_script('''(() => {
      const failure = ''' + json.dumps(failure) + ''';
      if (failure === 'getter') Object.defineProperty(window, 'localStorage', {
        get() { throw new DOMException('Denied', 'SecurityError'); }
      });
      else if (failure === 'invalid') localStorage.setItem('cms.sidebar.expanded', 'garbage');
      else Storage.prototype[failure] = () => { throw new DOMException('Denied', 'SecurityError'); };
    })()''')
    open_page(cms_page, '/history2')
    toggle = cms_page.locator('#cms-sidebar-toggle')
    assert toggle.get_attribute('aria-expanded') == 'true'
    assert not errors
    toggle.click()
    assert toggle.get_attribute('aria-expanded') == 'false'
    toggle.press('Space')
    assert toggle.get_attribute('aria-expanded') == 'true'
    assert not errors


@pytest.mark.parametrize('cms_desktop_case', CASES, indirect=True)
def test_sidebar_resize_keeps_plot_visible(cms_page, cms_desktop_case):
    api_requests = []
    cms_page.on('request', lambda request: api_requests.append(request.url)
          if '/api/' in request.url else None)
    open_page(cms_page, '/dashboard2?dataset=1')
    cms_page.wait_for_function("document.querySelector('#trend-chart')?.data?.length > 0")
    initial_requests = len(api_requests)
    initial_traces = cms_page.locator('#trend-chart').evaluate('node => JSON.stringify(node.data)')
    cms_page.evaluate('''async () => {
      window.shellEvents = [];
      document.addEventListener('cms:layout-change', event => shellEvents.push(event.detail));
      const shell = await import('/static/modules/core/cms-operations.js?v=task3');
      shell.initCmsShell(); shell.initCmsShell();
    }''')
    evidence = []
    for expected in ('false', 'true'):
        cms_page.locator('#cms-sidebar-toggle').click()
        assert cms_page.locator('#cms-sidebar-toggle').get_attribute('aria-expanded') == expected
        try:
            cms_page.wait_for_function('''() => [...document.querySelectorAll('.js-plotly-plot')]
              .filter(node => node.data?.length && node.getBoundingClientRect().width > 0)
              .every(node => {
                const parent = node.parentElement;
                const style = getComputedStyle(parent);
                const available = parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
                return Math.abs(node._fullLayout.width - available) <= 1;
              })''')
        finally:
            metrics = cms_page.evaluate('''() => [...document.querySelectorAll('.js-plotly-plot')]
              .filter(node => node.data?.length && node.getBoundingClientRect().width > 0)
              .map(node => {
                const parent = node.parentElement;
                const style = getComputedStyle(parent);
                return {id: node.id, plot: node._fullLayout.width, client: node.clientWidth,
                  parent: parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
                  parentClient: parent.clientWidth, padding: [style.paddingLeft, style.paddingRight],
                  traces: node.data.length, svg: !!node.querySelector('.main-svg')};
              })''')
            target = capture_page(cms_page, 'task3-plot-' + expected)
            target.with_suffix('.plot.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
        assert metrics and all(item['svg'] and item['traces'] > 0 for item in metrics)
        assert all(abs(item['plot'] - item['parent']) <= 1 for item in metrics)
        assert cms_page.locator('#trend-chart').evaluate('node => JSON.stringify(node.data)') == initial_traces
        assert len(api_requests) == initial_requests
        evidence.append(metrics)
        target = capture_page(cms_page, 'task3-plot-' + expected)
        target.with_suffix('.plot.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    assert cms_page.evaluate('shellEvents.length') == 2


def test_detail_scroll_restoration(cms_page):
    open_page(cms_page, '/dashboard2?dataset=1')
    cms_page.evaluate('scrollTo(0, 700)')
    cms_page.reload(wait_until='networkidle')
    cms_page.wait_for_function('scrollY === 0')
    assert cms_page.evaluate('history.scrollRestoration') == 'manual'
    cms_page.evaluate('''() => {
      scrollTo(0, 700);
      document.querySelector('#dataset-select').dispatchEvent(new Event('change', {bubbles: true}));
    }''')
    cms_page.wait_for_function('scrollY === 0')
    open_page(cms_page, '/history2')
    assert cms_page.evaluate('history.scrollRestoration') == 'auto'


@pytest.mark.parametrize('path,active', [
    ('/', '/equipment-status2'), ('/dashboard', '/equipment-status2'),
    ('/history', '/history2'), ('/dashboard_ui2', '/dashboard_ui6'), ('/main_sv', '/main_ct'),
    ('/static/index.html', '/equipment-status2'), ('/static/history.html', '/history2'),
    ('/static/equipment-status2.html', '/equipment-status2'),
    ('/static/kpi-dashboard-concept.html', '/dashboard_ui6'), ('/static/main-workspace.html', '/main_ct'),
])
def test_aliases_use_live_shell(cms_page, path, active):
    errors = []
    cms_page.on('pageerror', lambda error: errors.append(str(error)))
    response = open_page(cms_page, path)
    assert response.status == 200
    assert cms_page.locator('#cms-sidebar').count() == 1
    assert cms_page.locator('#cms-sidebar [aria-current="page"]').get_attribute('href') == active
    assert cms_page.locator('#cms-sidebar').bounding_box()['width'] == 244
    cms_page.locator('#cms-sidebar-toggle').click()
    assert cms_page.locator('#cms-sidebar').bounding_box()['width'] == 76
    assert cms_page.locator('#cms-sidebar-toggle').get_attribute('aria-expanded') == 'false'
    assert not errors
    capture_page(cms_page, 'task3-alias-' + (path.strip('/').replace('/', '-') or 'root'))