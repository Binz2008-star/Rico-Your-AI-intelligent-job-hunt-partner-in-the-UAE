import type { ReactElement } from "react";

type JsonLdData = Record<string, unknown>;

/**
 * Renders a JSON-LD <script> for structured data (schema.org).
 *
 * `data` is serialised with JSON.stringify — only trusted, code-defined objects
 * should be passed; never interpolate user input here.
 */
export function JsonLd({ data }: { data: JsonLdData | JsonLdData[] }): ReactElement {
    return (
        <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
        />
    );
}
