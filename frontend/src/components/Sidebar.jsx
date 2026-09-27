function Sidebar ({ activePage, onNavigate }) {
  const pages = ['Upload', 'Chat', 'Quiz', 'Settings']

  return (
    <nav className="sidebar">
      <h2 className="sidebar__title">Study Assistant</h2>
       <ul className="sidebar__nav">
        {pages.map((page) => (
          <li key={page}>
            <button 
            className={`sidebar__link ${activePage === page ? 'sidebar__link--active' : ''}`}
            onClick={() => onNavigate(page)}
            aria-current={activePage === page ? 'page' : undefined}
            >
              {page}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default Sidebar