# -*- coding: utf-8 -*-
import re

###################################################################################################

PLUGIN_TITLE = 'TV4 Play'
PLUGIN_PREFIX = '/video/tv4play'

PROGRAMS_XML = 'http://www.tv4play.se/?view=xml'
PROGRAMS_HTML = 'http://www.tv4play.se/%s'
PROGRAM_VIEWS_XML = 'http://www.tv4play.se/%s?view=xml'

NS_VIDEOAPI = {'v':'http://www.tv4.se/xml/videoapi'}
NS_CONTENTINFO = {'c':'http://www.tv4.se/xml/contentinfo'}

DATE_FORMAT = '%d/%m/%Y'
PLAYER_URL = 'http://plexapp.com/player/tv4play.php?id=%s'

CACHE_INTERVAL = CACHE_1HOUR
CACHE_INTERVAL_LONG = CACHE_1MONTH

# Default artwork and icon(s)
PLUGIN_ARTWORK = 'art-default.png'
PLUGIN_ICON_DEFAULT = 'icon-default.png'
PLUGIN_ICON_MORE = 'icon-more.png'

###################################################################################################

def Start():
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, PLUGIN_TITLE, PLUGIN_ICON_DEFAULT, PLUGIN_ARTWORK)
  Plugin.AddViewGroup('ListItems', viewMode='List', mediaType='items')

  # Set the default MediaContainer attributes
  MediaContainer.title1 = PLUGIN_TITLE
  MediaContainer.viewGroup = 'ListItems'
  MediaContainer.art = R(PLUGIN_ARTWORK)

  # Set the default cache time
  HTTP.CacheTime = CACHE_INTERVAL
  HTTP.Headers['User-agent'] = 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.10) Gecko/20100914 Firefox/3.6.10'

###################################################################################################

def UpdateCache():
  HTTP.Request(PROGRAMS_XML, cacheTime=CACHE_INTERVAL).content

###################################################################################################

def MainMenu():
  dir = MediaContainer()

  categories = XML.ElementFromURL(PROGRAMS_XML, encoding='utf-8', errors='ignore').xpath('/v:xml/v:category/v:subcategories/v:category[@level="1"]', namespaces=NS_VIDEOAPI)
  for category in categories:
    name = category.get('name')
    dir.Append(Function(DirectoryItem(TV4Programs, title=name, thumb=Function(GetThumb, name=name)), title=name, thumb=name))

  return dir

####################################################################################################

def TV4Programs(sender, title, thumb, use_xml=True, program_id=None):
  dir = MediaContainer(title2=title)

  # Use the 'main' XML file (www.tv4play.se/?view=xml) to display tv programs
  # This function (TV4Programs) is also used if we're deeper in the website and stumble upon an XML file that contains empty nodes for an extra level of 'subcategories'
  if use_xml:
    programs = XML.ElementFromURL(PROGRAMS_XML, encoding='utf-8', errors='ignore').xpath('/v:xml/v:category/v:subcategories/v:category[@name="'+title+'"]/v:subcategories/v:category[@level="2"]', namespaces=NS_VIDEOAPI)
    for program in programs:
      name = program.get('name')
      # We need the id of this program, unfortunately this isn't available in the XML file and we need to grab it from the program's home page
      # We don't do this here, since we only need the id if a user selects this tv program. Otherwise we'd have to loop over all the programs, which would increase load times
      url = program.xpath('./v:views/v:view/v:url', namespaces=NS_VIDEOAPI)[0].text
      url = re.findall('^(.+?)\?view=xml', url)[0]
      dir.Append(Function(DirectoryItem(TV4Views, title=name, thumb=Function(GetThumb, name=name, parent=thumb)), title=name, url=url, thumb=thumb))
  else:
    content = HTTP.Request( PROGRAMS_HTML % program_id ).content
    programs = XML.ElementFromString(content).xpath('//ul/li/div/p/a')
    for program in programs:
      # Cleanup the name
      name = program.text.strip().title()
      id = program.get('href')
      id = re.findall('^/(.+?)\?ajax', id)[0]
      url = PROGRAM_VIEWS_XML % id
      dir.Append(Function(DirectoryItem(TV4Views, title=name, thumb=Function(GetThumb, name=name, parent=thumb)), title=name, url=url, thumb=thumb, lookup_id=False))
  return dir

####################################################################################################

def TV4Views(sender, title, url, thumb, lookup_id=True):
  dir = MediaContainer(title2=title)

  # When we want to display the different views of a program, we first need to know what the id of that program is so we can download the right XML file.
  # But... we only know the program's name and url of its home page. The url is used here to find the program's id.
  if lookup_id == True:
    program_id = HTML.ElementFromURL(url, encoding='utf-8', errors='ignore', cacheTime=CACHE_INTERVAL_LONG).xpath('/html/body//div[@id="browser"]//ul[@class="breadcrumbs"]//li[last()]/h3/a')[0]
    program_id = program_id.get('href')
    program_id = re.findall('browser=([0-9\.]+)', program_id)[0]
    url = PROGRAM_VIEWS_XML % program_id

  # Get the page content first with HTTP.Request so we can check if we get something back
  content = HTTP.Request(url, cacheTime=CACHE_INTERVAL_LONG).content

  if content != None and content != '':
    views = XML.ElementFromString(content).xpath('/v:xml/v:category/v:views/v:view', namespaces=NS_VIDEOAPI)

    if len(views) > 0:
      # If there are views check to see if they're not empty nodes (like the ones for local news for example)
      if len( views[0].xpath('./*') ) > 0:
        for view in views:
          name = view.get('name')
          kind = view.get('kind')
          url = view.xpath('./v:url', namespaces=NS_VIDEOAPI)[0].text

          # Cleanup the name if it's all caps *and* the url contains the string 'keywords'
          if name.isupper() and url.find('keywords') != -1:
            name = name.title()

          # If the type of view is 'cliplist', the linked XML file contains videos
          if kind == 'cliplist':
            dir.Append(Function(DirectoryItem(TV4Videos, title=name, thumb=Function(GetThumb, name=name, parent=thumb)), title=name, url=url))
          # If the type of view is categorylist, we have to iterate at least onces more over the contents of the linked XML file
          # In this case we don't need to look for an id, instead we can use the provided link (which contains an id)
          elif kind == 'categorylist':
            dir.Append(Function(DirectoryItem(TV4Views, title=name, thumb=Function(GetThumb, name=name, parent=thumb)), title=name, url=url, thumb=thumb, lookup_id=False))
      else:
        # If the nodes do not contain any childs, try to use information from the piece of HTML code that's used on the website in XHR
        # This means that there's probably an extra level of subcategories
        dir = TV4Programs(sender, title, thumb, use_xml=False, program_id=program_id)

  return dir

####################################################################################################

def TV4Videos(sender, title, url, page=1):
  dir = MediaContainer(title2=title)

  videoContent = XML.ElementFromURL(url + '&page=' + str(page), encoding='utf-8', errors='ignore')

  videos = videoContent.xpath('/c:xml/c:contentList/c:content', namespaces=NS_CONTENTINFO)
  for video in videos:
    # Filter to display free content only (although the website doesn't contain paid content at the moment - Nov 28, 2009)
    requiresPayment = video.xpath('./c:requiresPayment', namespaces=NS_CONTENTINFO)[0].text

    if requiresPayment == 'false':
      contentId = video.get('contentID')
      image = video.xpath('./c:imageURL', namespaces=NS_CONTENTINFO)[0].text
      vtitle = video.xpath('./c:title', namespaces=NS_CONTENTINFO)[0].text
      date = video.xpath('./c:publishedDate', namespaces=NS_CONTENTINFO)[0].text
      date = Datetime.ParseDate(date).strftime(DATE_FORMAT)

      dir.Append(WebVideoItem(PLAYER_URL % contentId, title=vtitle, infolabel=date, thumb=image))

  # Check to see if there's more than one page with videos. If so, add a 'More' item to the list
  pagination = videoContent.xpath('/c:xml/c:contentList', namespaces=NS_CONTENTINFO)[0].get('page')
  if pagination != None:
    pagination = re.findall('Page ([0-9]+) of ([0-9]+)', pagination)
    if len(pagination) > 0 and ( int(pagination[0][0]) < int(pagination[0][1]) ):
      dir.Append(Function(DirectoryItem(TV4Videos, title='Mer ...', thumb=R(PLUGIN_ICON_MORE)), title=title, url=url, page=page+1))

  return dir

####################################################################################################

def GetThumb(name=None, parent=None):
  if name == 'Aktualitet':
    return Redirect( R('icon-Aktualitet.png') )
  elif name == 'Hem & fritid':
    return Redirect( R('icon-HemOchFritid.png') )
  elif name == 'Nyheter':
    return Redirect( R('icon-Nyheter.png') )
  elif name == 'Nöje & humor':
    return Redirect( R('icon-NojeOchHumor.png') )
  elif name == 'Sport':
    return Redirect( R('icon-Sport.png') )
  elif name == 'Fotbollskanalen':
    return Redirect( R('icon-Fotbollskanalen.png') )
  elif name == 'Hockeykanalen':
    return Redirect( R('icon-Hockeykanalen.png') )
  elif name == 'Lattjo lajban':
    return Redirect( R('icon-LattjoLajban.png') )
  elif name == 'Barn':
    return Redirect( R(PLUGIN_ICON_DEFAULT) )
  elif parent != None:
    return GetThumb(name=parent)
  else:
    return Redirect( R(PLUGIN_ICON_DEFAULT) )
