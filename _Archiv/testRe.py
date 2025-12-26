import re

opf = '<dc:creator opf:file-as="Attanasio, A. A." opf:role="aut">A. A. Attanasio</dc:creator>'

author_pattern = re.search(r'<dc:creator.*?>(.*?)</dc:creator>', opf)
if author_pattern:
    author = author_pattern.group(1).strip()
    print(author)

    # Sicherstellen, dass re.search nicht fehlschlägt
    match = re.search(r',', author)
    print(match)
    if match:
        print("Komma at", match.start())
        if match.start() > 0:
            print(author)
    else:
        print("No Komma")
        names = re.split(r'\s', author)
        print(names)
        print(len(names))
        if len(names) == 1:
            print(names[1] + ", " + names[0])
        elif len(names) > 1:
            n = names[0]
            for i in range(1,len(names)-1):
                n = n + " " + names[i]
            print( names[len(names)-1] + ", " + n)
        else:
            print(len(names), names)
            print(names[0])