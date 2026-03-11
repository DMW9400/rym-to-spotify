#!/usr/bin/env -S uv run

import sys
import re
import json
import time
import asyncio

from html import unescape
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from nodriver import start, Browser, Tab
from nodriver.core.connection import ProtocolException


def sanitize_filename(filename):
    """Remove invalid characters for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()


def clean_song_name(song, artist, album):
    """
    Clean up the song title by:
      - Removing occurrences of the artist and album names,
      - Removing unwanted phrases and patterns like official video tags,
        full album/compilation markers, lyrics, audio hints, etc.
      - Trimming extra punctuation and whitespace.
    """
    original = song  # For debugging if needed.

    # Remove occurrences of artist and album names (case-insensitive)
    song = re.sub(re.escape(artist), "", song, flags=re.IGNORECASE)
    song = re.sub(re.escape(album), "", song, flags=re.IGNORECASE)

    # Remove content in parentheses or braces that contain unwanted keywords.
    unwanted_in_brackets = [
        r'\bofficial\b', r'\bremaster(ed)?\b', r'\bvideo\b',
        r'\baudio\b', r'\bclip\b', r'\blyrics\b', r'\bfull\s*album\b',
        r'\bcompilation\b'
    ]
    # Build a regex pattern that finds any unwanted keyword inside parentheses/braces.
    pattern = r'[\(\{][^)\}]*(' + '|'.join(unwanted_in_brackets) + r')[^)\}]*[\)\}]'
    song = re.sub(pattern, '', song, flags=re.IGNORECASE)

    # Remove unwanted phrases outside brackets.
    unwanted_phrases = [
        "official video", "official music video", "video clip", "video official",
        "remastered", "official audio", "full album", "compilation", "lyrics", "audio"
    ]
    for phrase in unwanted_phrases:
        song = re.sub(re.escape(phrase), '', song, flags=re.IGNORECASE)

    # Remove extraneous quotation marks
    song = song.replace('"', '').replace("''", '')

    # Remove extra separator characters (hyphens, colons, etc.) at the beginning or end.
    song = re.sub(r"^[\s\-–:]+", "", song)
    song = re.sub(r"[\s\-–:]+$", "", song)

    # Replace multiple spaces with a single space.
    song = re.sub(r"\s{2,}", " ", song)

    return song.strip()


def is_chart_url(url):
    return '/charts/' in url


async def wait_for_content(tab, check_text, timeout=60):
    """Wait until check_text appears in the page source, polling every 2 seconds."""
    for _ in range(timeout // 2):
        await asyncio.sleep(2)
        try:
            html = await tab.evaluate("document.documentElement.outerHTML")
        except Exception:
            continue
        if check_text in html:
            return
    print(f"Warning: timed out after {timeout}s waiting for content to load")


async def get_page_source(tab):
    try:
        return await tab.get_content()
    except ProtocolException:
        await asyncio.sleep(1)
        return await tab.evaluate("document.documentElement.outerHTML")


def parse_chart_items(soup):
    """Parse album/artist entries from a RYM chart page."""
    items = []
    chart_entries = soup.find_all('div', class_='page_charts_section_charts_item')

    for entry in chart_entries:
        # Extract album title
        title_link = entry.find('a', class_='page_charts_section_charts_item_link')
        if not title_link:
            continue
        title_locale = title_link.find('span', class_='ui_name_locale_original')
        album_title = title_locale.get_text().strip() if title_locale else title_link.get_text().strip()

        # Extract artist
        artist_div = entry.find('div', class_='page_charts_section_charts_item_credited_text')
        if not artist_div:
            continue
        artist_link = artist_div.find('a', class_='artist')
        if not artist_link:
            continue
        artist_locale = artist_link.find('span', class_='ui_name_locale_original')
        artist = artist_locale.get_text().strip() if artist_locale else artist_link.get_text().strip()

        # Extract release type
        type_tag = entry.find('span', class_='page_charts_section_charts_item_release_type')
        item_type = type_tag.get_text().strip() if type_tag else "Album"

        # Extract Spotify ID from data-links attribute
        spotify_id = None
        media_div = entry.find('div', attrs={'data-medialink': 'true'})
        if media_div and media_div.get('data-links'):
            try:
                links_data = json.loads(unescape(media_div['data-links']))
                if 'spotify' in links_data:
                    for sid, info in links_data['spotify'].items():
                        spotify_id = sid
                        break
            except (json.JSONDecodeError, KeyError):
                pass

        items.append((artist, album_title, item_type, spotify_id))

    return items


def parse_list_items(soup):
    """Parse album/artist entries from a RYM list page."""
    items = []
    list_table = soup.find('table', id='user_list')
    if not list_table:
        return None  # Signal that the table wasn't found

    list_rows = list_table.find_all(
        'tr',
        class_=lambda c: c and ('trodd' in c or 'treven' in c)
    )

    for item in list_rows:
        if 'list_mobile_description' in item.get('class', []):
            continue
        if item.find(class_='generic_item'):
            continue

        artist_tag = item.find('h2')
        if not artist_tag:
            continue
        artist_link = artist_tag.find('a', class_='list_artist')
        if not artist_link:
            continue
        artist = artist_link.get_text().strip()

        title_tag = item.find('h3')
        if not title_tag:
            continue
        title_link = title_tag.find('a', class_='list_album')
        if not title_link:
            continue
        album_title = title_link.get_text().strip()
        href = title_link.get('href', '')

        if '/release/' not in href:
            continue

        rel_date_tag = title_tag.find('span', class_='rel_date')
        if rel_date_tag:
            type_info = rel_date_tag.get_text().strip()
            if "[EP]" in type_info:
                item_type = "EP"
            elif "[Compilation]" in type_info:
                item_type = "Compilation"
            elif "[Single]" in type_info:
                item_type = "Single"
            else:
                item_type = "Album"
        else:
            item_type = "Album"

        # Check for song links (youtube, spotify, bandcamp)
        song_link = None
        for a in item.find_all('a'):
            if a == artist_link or a == title_link:
                continue
            href_candidate = a.get('href', '')
            if any(domain in href_candidate for domain in ['youtube.com', 'spotify.com', 'bandcamp.com']):
                song_link = a
                break

        song_name = None
        if song_link:
            youtube_title_elem = song_link.find('div', class_='youtube_title')
            if youtube_title_elem:
                song_text = youtube_title_elem.get_text().strip()
            else:
                song_text = song_link.get_text(separator=" ", strip=True)
                unwanted = ["Listen", "video clip", "video official", "remastered", "audio", "lyrics"]
                for word in unwanted:
                    song_text = song_text.replace(word, "")
                song_text = song_text.strip()

            cleaned = clean_song_name(song_text, artist, album_title)
            if cleaned and not any(x in song_text.lower() for x in ["full album", "compilation", "album only"]):
                song_name = cleaned

        items.append((artist, album_title, item_type, song_name))

    return items


def find_next_page(soup, is_chart):
    """Find the next page link, returns href or None."""
    if is_chart:
        next_link = soup.find('a', class_='ui_pagination_next')
        if next_link and 'disabled' not in next_link.get('class', []):
            return next_link.get('href', '')
    else:
        next_link = soup.find('a', class_='navlinknext')
        if next_link:
            return next_link.get('href', '')
    return None


async def scrape_rym(url):
    if not url.startswith('https://rateyourmusic.com/'):
        print("Error: Please provide a valid RateYourMusic URL")
        sys.exit(1)

    is_chart = is_chart_url(url)
    base_url = url
    results = []
    current_url = base_url
    output_filename = None

    for attempt in range(3):
        try:
            browser: Browser = await start(no_sandbox=True)
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"Browser connection failed (attempt {attempt + 1}/3), retrying...")
            await asyncio.sleep(2)
    tab: Tab = await browser.get(current_url)

    title_extracted = False
    page_num = 1

    # Choose the text to look for based on page type
    content_marker = 'page_charts_section_charts_item' if is_chart else 'id="user_list"'

    while True:
        print(f"Waiting for page {page_num} to load...")
        await wait_for_content(tab, content_marker)

        page_source = await get_page_source(tab)
        soup = BeautifulSoup(page_source, 'html.parser')

        if not title_extracted:
            header_tag = soup.find('h1')
            if is_chart:
                list_title = header_tag.get_text().strip() if header_tag else "Unknown"
                output_filename = sanitize_filename(f"{list_title}.txt")
                results.append(f'title: "{list_title}"')
            else:
                list_title = header_tag.get_text().strip() if header_tag else "Unknown"
                user_tag = soup.find('a', class_='user')
                username = user_tag.get_text().strip() if user_tag else "Unknown"
                output_filename = sanitize_filename(f"{list_title} - {username}.txt")
                results.append(f'title: "{list_title} - {username}"')
            results.append(f'url: "{base_url}"')
            title_extracted = True

        if is_chart:
            items = parse_chart_items(soup)
            if not items:
                print("No chart items found on page. Stopping.")
                break
            for artist, album_title, item_type, spotify_id in items:
                line = f'{item_type.lower()}: "{album_title}" - "{artist}"'
                if spotify_id:
                    line += f' [spotify:{spotify_id}]'
                results.append(line)
            print(f"Page {page_num}: found {len(items)} items")
        else:
            items = parse_list_items(soup)
            if items is None:
                print("Table #user_list not found on page. Retrying...")
                continue
            for artist, album_title, item_type, song_name in items:
                if song_name:
                    results.append(f'song: "{song_name}" - "{album_title}" - "{artist}"')
                else:
                    results.append(f'{item_type.lower()}: "{album_title}" - "{artist}"')
            print(f"Page {page_num}: found {len(items)} items")

        next_href = find_next_page(soup, is_chart)
        if next_href:
            current_url = urljoin(base_url, next_href)
            print(f"Moving to next page: {current_url}")
            await tab.get(current_url)
            await asyncio.sleep(1)
            page_num += 1
        else:
            print("No next page found. Scraping complete.")
            break

    if output_filename:
        with open(output_filename, 'w', encoding='utf-8') as f:
            for item in results:
                f.write(item + '\n')
        print(f"Scraping complete. {len(results)} items written to {output_filename}")
    else:
        print("Error: Could not determine output filename")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rym-to-txt.py <RYM_URL>")
        print("Example: python rym-to-txt.py https://rateyourmusic.com/list/M4rcus/dream-folk/")
        print("         python rym-to-txt.py https://rateyourmusic.com/charts/top/album/2010s/")
        sys.exit(1)

    rym_url = sys.argv[1]
    asyncio.run(scrape_rym(rym_url))
