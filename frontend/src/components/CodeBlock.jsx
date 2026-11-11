export default function CodeBlock({ children, title }) {
  return (
    <div className="code-block">
      {title ? <div className="code-title">{title}</div> : null}
      <pre>
        <code>{children}</code>
      </pre>
    </div>
  );
}
