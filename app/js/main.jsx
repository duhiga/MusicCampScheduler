var Navbar = window.ReactBootstrap.Navbar;
var Nav = window.ReactBootstrap.Nav;
var NavItem = window.ReactBootstrap.NavItem;
var NavDropdown = window.ReactBootstrap.NavDropdown;
var MenuItem = window.ReactBootstrap.MenuItem;
var Accordion = window.ReactBootstrap.Accordion;
var Panel = window.ReactBootstrap.Panel;

const navbarInstance = (
  <Navbar inverse collapseOnSelect>
    <Navbar.Header>
      <Navbar.Brand>
        <a href="#">React-Bootstrap</a>
      </Navbar.Brand>
      <Navbar.Toggle />
    </Navbar.Header>
    <Navbar.Collapse>
      <Nav>
        <NavItem eventKey={1} href="#">Link</NavItem>
        <NavItem eventKey={2} href="#">Link</NavItem>
        <NavDropdown eventKey={3} title="Dropdown" id="basic-nav-dropdown">
          <MenuItem eventKey={3.1}>Action</MenuItem>
          <MenuItem eventKey={3.2}>Another action</MenuItem>
          <MenuItem eventKey={3.3}>Something else here</MenuItem>
          <MenuItem divider />
          <MenuItem eventKey={3.3}>Separated link</MenuItem>
        </NavDropdown>
      </Nav>
      <Nav pullRight>
        <NavItem eventKey={1} href="#">Link Right</NavItem>
        <NavItem eventKey={2} href="#">Link Right</NavItem>
      </Nav>
    </Navbar.Collapse>
  </Navbar>
);

ReactDOM.render(
    navbarInstance, 
    document.querySelector('#navbar-container')
);

const ScheduleAccordionInstance = (props) => (
    <Accordion>
        { props.schedule.map(period => (
            <Panel header={ period.title } eventKey={ period.id }>
                { period.content }
            </Panel>
        )) }
    </Accordion>
);

let schedule = [
    { id: 1, title: "The First Title", content: "The First Content" },
    { id: 2, title: "The Second Title", content: "The Second Content" }
];

ReactDOM.render(
    <ScheduleAccordionInstance schedule={ schedule } />,
    document.querySelector('#schedule-container')
);