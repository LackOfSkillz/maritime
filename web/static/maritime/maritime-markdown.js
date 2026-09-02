/* A small markdown renderer, for the handbook and nothing else.
 *
 * **Why not a library.** The handbook has to work with no network, inside a game client's
 * content policy, and with the server down - it is static files and a browser. Pulling a
 * megabyte of general-purpose parser off a CDN to render fifteen pages of prose we wrote
 * ourselves would trade all three of those for a feature nobody asked for.
 *
 * So this handles the subset the handbook actually uses, and handles it strictly: headings,
 * paragraphs, lists, tables, fenced and indented code, block quotes, horizontal rules, and
 * inline emphasis, code and links. Anything it does not recognise comes out as text, which
 * is the right failure for a manual - a stray asterisk is a blemish, and a silently dropped
 * paragraph is a lie.
 *
 * **Everything is escaped first.** The input is ours, but "the input is ours" is what every
 * injection begins with, and a help page that renders arbitrary HTML is a help page that
 * will one day render somebody else's.
 */
window.MaritimeMarkdown = (function () {
    "use strict";

    function escaped(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    /* Inline: code first, because what is inside a span of code is not markup.
     *
     * The code spans are lifted out and replaced with placeholders before anything else
     * runs, then put back at the end. Without that, `*` inside `code` becomes emphasis and
     * a page explaining a wildcard renders as italics. */
    function inline(text) {
        /* The placeholder is a character that cannot occur in the escaped text it
         * stands in. An earlier version used a bare number between spaces, which ate
         * every ordinary number in the prose - "at 40 metres" became span forty,
         * which does not exist. */
        var spans = [];
        var out = escaped(text).replace(/`([^`]+)`/g, function (whole, code) {
            spans.push(code);
            return "\u0000" + (spans.length - 1) + "\u0000";
        });

        out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (whole, label, href) {
            /* Only the two shapes the handbook uses: a sibling page, and an ordinary
             * absolute link. Anything else is left as text rather than turned into a link
             * that goes somewhere unexpected. */
            if (/^[a-z0-9-]+\.md$/i.test(href) || /^https?:\/\//i.test(href)
                || /^[.a-z0-9/_-]+\.md$/i.test(href)) {
                return '<a href="' + href + '">' + label + "</a>";
            }
            return label;
        });

        out = out
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");

        return out.replace(/\u0000(\d+)\u0000/g, function (whole, index) {
            return "<code>" + escaped(spans[Number(index)]) + "</code>";
        });
    }

    function tableRow(line) {
        return line
            .replace(/^\s*\|/, "")
            .replace(/\|\s*$/, "")
            .split("|")
            .map(function (cell) {
                return cell.trim();
            });
    }

    function isDivider(line) {
        return /^\s*\|?[\s:-]*-[\s:|-]*\|?\s*$/.test(line) && line.indexOf("-") !== -1;
    }

    function render(source) {
        var lines = String(source).replace(/\r\n/g, "\n").split("\n");
        var out = [];
        var index = 0;

        function flushParagraph(buffer) {
            if (buffer.length) {
                out.push("<p>" + inline(buffer.join(" ")) + "</p>");
                buffer.length = 0;
            }
        }

        var paragraph = [];

        while (index < lines.length) {
            var line = lines[index];

            /* Fenced code. Taken verbatim: no inline rules run inside it. */
            if (/^```/.test(line)) {
                flushParagraph(paragraph);
                var fenced = [];
                index += 1;
                while (index < lines.length && !/^```/.test(lines[index])) {
                    fenced.push(lines[index]);
                    index += 1;
                }
                index += 1;
                out.push("<pre><code>" + escaped(fenced.join("\n")) + "</code></pre>");
                continue;
            }

            /* Indented code, which is how the handbook shows what to type. */
            if (/^ {4}\S/.test(line)) {
                flushParagraph(paragraph);
                var block = [];
                while (index < lines.length
                       && (/^ {4}/.test(lines[index]) || lines[index].trim() === "")) {
                    if (lines[index].trim() === ""
                        && !(index + 1 < lines.length && /^ {4}\S/.test(lines[index + 1]))) {
                        break;
                    }
                    block.push(lines[index].replace(/^ {4}/, ""));
                    index += 1;
                }
                out.push("<pre><code>" + escaped(block.join("\n")) + "</code></pre>");
                continue;
            }

            if (/^\s*$/.test(line)) {
                flushParagraph(paragraph);
                index += 1;
                continue;
            }

            if (/^---+\s*$/.test(line)) {
                flushParagraph(paragraph);
                out.push("<hr>");
                index += 1;
                continue;
            }

            var heading = line.match(/^(#{1,4})\s+(.*)$/);
            if (heading) {
                flushParagraph(paragraph);
                var level = heading[1].length;
                out.push("<h" + level + ">" + inline(heading[2]) + "</h" + level + ">");
                index += 1;
                continue;
            }

            /* Tables: a header row, a divider, then body rows. */
            if (line.indexOf("|") !== -1 && index + 1 < lines.length
                && isDivider(lines[index + 1])) {
                flushParagraph(paragraph);
                var head = tableRow(line);
                index += 2;
                var body = [];
                while (index < lines.length && lines[index].indexOf("|") !== -1
                       && lines[index].trim() !== "") {
                    body.push(tableRow(lines[index]));
                    index += 1;
                }
                out.push(
                    "<table><thead><tr>"
                    + head.map(function (cell) { return "<th>" + inline(cell) + "</th>"; }).join("")
                    + "</tr></thead><tbody>"
                    + body.map(function (row) {
                        return "<tr>" + row.map(function (cell) {
                            return "<td>" + inline(cell) + "</td>";
                        }).join("") + "</tr>";
                    }).join("")
                    + "</tbody></table>"
                );
                continue;
            }

            /* Lists, bulleted or numbered.
             *
             * The numbered case was missing to begin with, so a numbered contents fell
             * through to the paragraph accumulator and came out as one long run-on line -
             * while the repository, rendering the same file, showed it correctly. Two
             * faces of one source disagreeing is the exact failure this design exists to
             * prevent, so the omission mattered more here than it would elsewhere. */
            var bullet = /^\s*[-*]\s+/;
            var numbered = /^\s*\d+\.\s+/;
            var marker = bullet.test(line) ? bullet : (numbered.test(line) ? numbered : null);
            if (marker) {
                flushParagraph(paragraph);
                var ordered = marker === numbered;
                var items = [];
                while (index < lines.length && marker.test(lines[index])) {
                    var item = lines[index].replace(marker, "");
                    index += 1;
                    /* A wrapped bullet: continuation lines are indented and are part of the
                     * same item, not a new paragraph. */
                    while (index < lines.length && /^\s{2,}\S/.test(lines[index])
                           && !marker.test(lines[index])) {
                        item += " " + lines[index].trim();
                        index += 1;
                    }
                    items.push("<li>" + inline(item) + "</li>");
                }
                out.push(
                    (ordered ? "<ol>" : "<ul>")
                    + items.join("")
                    + (ordered ? "</ol>" : "</ul>")
                );
                continue;
            }

            if (/^>\s?/.test(line)) {
                flushParagraph(paragraph);
                var quoted = [];
                while (index < lines.length && /^>\s?/.test(lines[index])) {
                    quoted.push(lines[index].replace(/^>\s?/, ""));
                    index += 1;
                }
                out.push("<blockquote>" + inline(quoted.join(" ")) + "</blockquote>");
                continue;
            }

            paragraph.push(line.trim());
            index += 1;
        }

        flushParagraph(paragraph);
        return out.join("\n");
    }

    return { render: render };
})();
