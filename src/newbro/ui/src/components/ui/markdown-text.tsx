import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "../../lib/utils";

const markdownComponents: Components = {
  a({ node, ...props }) {
    return (
      <a
        {...props}
        className={cn("break-words text-primary underline decoration-primary/35 underline-offset-2", props.className)}
        rel="noreferrer"
        target="_blank"
      />
    );
  },
  code({ node, ...props }) {
    return (
      <code
        {...props}
        className={cn(
          "rounded bg-muted/75 px-1 py-0.5 font-mono text-[0.92em] text-foreground break-words",
          props.className,
        )}
      />
    );
  },
  pre({ node, ...props }) {
    return (
      <pre
        {...props}
        className={cn(
          "my-2 max-w-full overflow-x-auto rounded-md bg-muted/75 p-2 font-mono text-[11px] leading-5 text-foreground",
          props.className,
        )}
      />
    );
  },
  p({ node, ...props }) {
    return <p {...props} className={cn("my-2 break-words", props.className)} />;
  },
  ul({ node, ...props }) {
    return <ul {...props} className={cn("my-2 list-disc space-y-1 pl-5", props.className)} />;
  },
  ol({ node, ...props }) {
    return <ol {...props} className={cn("my-2 list-decimal space-y-1 pl-5", props.className)} />;
  },
  li({ node, ...props }) {
    return <li {...props} className={cn("pl-0.5", props.className)} />;
  },
  blockquote({ node, ...props }) {
    return (
      <blockquote
        {...props}
        className={cn("my-2 border-l-2 border-border pl-3 text-muted-foreground", props.className)}
      />
    );
  },
  table({ node, ...props }) {
    return (
      <table
        {...props}
        className={cn("my-2 block max-w-full overflow-x-auto border-collapse text-left text-[0.95em]", props.className)}
      />
    );
  },
  th({ node, ...props }) {
    return <th {...props} className={cn("border border-border px-2 py-1 font-medium", props.className)} />;
  },
  td({ node, ...props }) {
    return <td {...props} className={cn("border border-border px-2 py-1 align-top", props.className)} />;
  },
};

export function MarkdownText({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0 max-w-full overflow-hidden [&>:first-child]:mt-0 [&>:last-child]:mb-0", className)}>
      <ReactMarkdown
        disallowedElements={["img"]}
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
