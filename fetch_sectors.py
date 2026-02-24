import os
import json
import urllib.request
from bs4 import BeautifulSoup
import ssl

def main():
    print("Fetching sub-sectors from İş Yatırım 'Temel-Degerler-Ve-Oranlar' page...")
    
    # Bypass SSL verification if needed for MacOS python environments
    ssl._create_default_https_context = ssl._create_unverified_context
    url = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx"
    
    sector_map = {}
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the specific table with id summaryBasicData
            table = soup.find('table', {'id': 'summaryBasicData'})
            if table:
                tbody = table.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        tds = tr.find_all('td')
                        if len(tds) >= 3:
                            ticker = tds[0].get_text(strip=True)
                            sector = tds[2].get_text(strip=True)
                            # Remove non-breaking spaces or trailing spaces
                            sector = sector.replace('\xa0', '').strip()
                            if ticker and sector:
                                sector_map[ticker] = sector
            else:
                print("Error: Could not find 'summaryBasicData' table in the HTML.")
                return

    except Exception as e:
        print(f"Error fetching data from İş Yatırım: {e}")
        return
        
    if not sector_map:
        print("Warning: No sectors were parsed. Check HTML structure.")
        return
        
    print(f"Successfully successfully fetched sub-sectors for {len(sector_map)} tickers.")
    
    # Save to a JSON file in the bist_valuation_app directory
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sectors.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(sector_map, f, indent=4, ensure_ascii=False)
    print(f"Done. Saved sectors to {out_path}.")

if __name__ == '__main__':
    main()
