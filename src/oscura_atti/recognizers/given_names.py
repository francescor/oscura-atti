"""Common given names (Italy first, then other European countries and the largest foreign
communities living in Italy). Lower case, without accents.

Used to tell a person ("ROSSI Mario", "Mario Rossi") from a heading or an organisation
("DIFESA Civile", "COMANDO Provinciale") when there is no other contextual cue.
"""

from __future__ import annotations

_IT_M = """
abele achille adalberto adelmo adolfo adriano agostino aldo alessandro alessio alfio alfredo alberto albino
alvise amedeo amerigo amos andrea angelo annibale anselmo antonino antonio arcangelo ardito aristide armando
arnaldo arrigo arturo attilio augusto aurelio bartolomeo battista benedetto beniamino benito bernardo bertrando
biagio bortolo bruno camillo carlo carmelo carmine cesare christian cirillo claudio clemente corrado cosimo
cristian cristiano cristoforo damiano daniele dante dario davide demetrio denis diego dino domenico donato
duilio edoardo egidio elia elio emanuele emiliano emilio enea enrico enzo ercole ermanno ernesto ettore eugenio
ezio fabiano fabio fabrizio federico felice ferdinando fernando ferruccio filippo fiorenzo flavio francesco
franco fulvio gabriele gaetano galdino gastone gennaro giacomo giampaolo giampiero giancarlo gianfranco
gianluca gianluigi gianmarco gianni gianpaolo gianpietro gilberto gino giordano giorgio giovanni girolamo
giuliano giulio giuseppe graziano gregorio guido ignazio igor italo ivan ivano ivo jacopo lamberto lauro lazzaro
leonardo leone leopoldo lino livio lorenzo luca luciano lucio luigi manfredi manlio manuel marcello marco mariano
mario marino martino massimiliano massimo matteo mattia maurizio mauro michele mirco mirko moreno nazzareno
nello nereo nicola nicolo nino norberto oddone omar orazio oreste orlando oscar osvaldo ottavio pasquale
patrizio paolo pierangelo pierluigi piero pierpaolo pietro primo raffaele raimondo renato renzo riccardo
rinaldo rino roberto rocco rodolfo romano romeo romolo rosario ruggero salvatore samuele sandro santo saverio
sebastiano secondo sergio severino silvano silvio simone stefano tarcisio teodoro tiziano tommaso tullio
ubaldo ugo umberto valentino valerio vasco vincenzo virgilio vito vittorio walter zeno ennio eros loris
nevio dorino gianantonio giannantonio gianbattista giambattista giovanbattista luigino valter danilo
gioele alessio ettore leandro nazario
"""
_IT_F = """
ada adele adriana agata agnese alba albertina alessandra alessia alice alma amalia ambra angela angelica
angelina anita anna annalisa annamaria antonella antonia arianna assunta aurora barbara beatrice benedetta
bianca bruna camilla carla carlotta carmela carmen carolina caterina cecilia celeste chiara cinzia clara
claudia clelia concetta cristina daniela debora delia denise diana dina donatella dora edda elena eleonora
elisa elisabetta elsa emanuela emma enrica erica erika ermelinda erminia ester eugenia eva fabiana fabiola
federica fernanda filomena fiorella flavia franca francesca gabriella gaia gemma georgia giada gianna
gilda gina ginevra gioia giorgia giovanna gisella giulia giuliana giuseppina gloria grazia graziella
ida ilaria ines irene iris isabella ivana jessica laura lea lidia liliana lina linda livia loredana lorena
lorenza luana lucia luciana luigia luisa maddalena manuela mara marcella margherita maria mariagrazia
mariangela marianna mariarosa marica marina marisa marta martina matilde maura melania michela milena
mirella miriam monica nadia natalia nicoletta nives noemi norma ornella orietta paola patrizia piera
pierina rachele raffaella rebecca regina renata rina rita roberta romina rosa rosalba rosanna rosaria
rossana rosella rosetta sabrina samanta sandra sara serena silvana silvia simona sofia sonia stefania
susanna tamara teresa tiziana valentina valeria vanessa vera veronica viola virginia vittoria wanda
wilma zaira agostina albina amelia annunziata bertilla brigida candida carmelina dolores elda elvira
emilia ernesta felicita fiorenza flora gemma giannina iolanda italia lucrezia luigina marcellina mafalda
nella ofelia olga palmira pia rina santina tecla tosca ursula vilma luana mariateresa mariagiovanna
marialuisa mariarita annarosa annachiara marialaura
"""
_OTHER = """
john james robert michael william david richard joseph thomas charles christopher daniel matthew anthony
mark donald steven paul andrew joshua kenneth kevin brian george timothy ronald edward jason jeffrey ryan
jacob gary nicholas eric jonathan stephen larry justin scott brandon benjamin samuel gregory alexander
patrick frank raymond jack dennis jerry tyler aaron jose adam nathan henry peter harry oliver charlie
mary patricia jennifer linda elizabeth susan jessica sarah karen lisa nancy betty margaret sandra ashley
kimberly emily donna michelle carol amanda dorothy melissa deborah stephanie rebecca sharon laura cynthia
kathleen amy angela shirley anna brenda pamela emma nicole helen samantha katherine christine catherine
olivia sophie charlotte amelia isla poppy
juan carlos jose luis manuel javier miguel francisco jesus pedro alejandro rafael fernando pablo sergio
jorge alberto alvaro diego adrian raul enrique ramon vicente andres joaquin santiago ignacio maria carmen
josefa isabel dolores pilar teresa rosario mercedes lucia cristina marta elena paula raquel beatriz
jean pierre michel philippe alain nicolas christophe patrick frederic laurent stephane sebastien julien
francois olivier thierry eric pascal marie nathalie isabelle sylvie catherine francoise valerie sandrine
christine celine aurelie camille julie juliette chloe
hans peter klaus wolfgang jurgen dieter uwe stefan andreas thomas michael frank markus matthias sabine
ursula monika petra andrea claudia susanne birgit katrin anja heike gisela helga
mohamed mohammed muhammad ahmed ahmad ali omar youssef hassan hussein karim mustafa abdel abdul rachid
said khalid hamza ibrahim ismail mahmoud yassine amine fatima aisha khadija amina salma zahra meryem nadia
samira leila ion ioan andrei mihai alexandru gheorghe vasile florin adrian marius cristian ionut bogdan
elena maria ioana mihaela andreea alina gabriela daniela florentina valentina
ivan dmitri sergei oleksandr olena natalia svetlana tatiana irina olga yulia
arben ardian besnik blerim gentian ilir kujtim fatmir mirela elona ervis klodian
wei ming jing hui xin yan lei jun hong
raj ravi amit sunil anil sanjay priya sunita
mamadou moussa cheikh ibrahima abdoulaye ousmane amadou modou babacar fatou aminata awa mariama aissatou
kwame kofi kwabena kwaku yaw akua ama abena adwoa efua emmanuel isaac
chinedu emeka ngozi chioma oluwaseun adebayo tunde folake blessing precious favour godwin osagie uche ifeoma
efosa osas omoregie nosa osaro eghosa
abdelaziz abdellah abderrahim abdelkader rachida latifa naima hafsa soukaina zineb hamid driss jamal
youness reda anas ilyas adam sara
arjan ermal flamur gjergj kastriot shkelzen valon xhevat agim bujar ermira mimoza valbona drita
gheorghe ionel costel dorin sorin viorel nicolae ilie lucian ovidiu raluca roxana oana corina simona
liudmyla nataliya oksana iryna halyna mykola vasyl petro taras bohdan volodymyr yaroslav serhii
gurpreet harpreet manpreet jaspreet kuldeep sukhwinder amandeep baljit harjinder paramjit rajinder
imran asif tariq bilal usman zahid shahid naveed sajid aamir rizwan
mohammad rahim karim hasan hossain shahin mizanur rafiq jahid nasrin shirin
xiaoming xiaoli xiaohong wenjun jianguo zhiwei yufei meiling lihua weiwei
"""

GIVEN_NAMES: frozenset[str] = frozenset((_IT_M + _IT_F + _OTHER).split())

# Given names that are also ordinary words, place names or saints: not enough on their own to
# make "Name Surname" a person when there is no other cue ("Santo Stefano", "Marina Militare").
AMBIGUOUS: frozenset[str] = frozenset("""
santo santa felice vittoria speranza gioia fortunato benedetto sole marina rosa viola grazia luce pace
fiore celeste bianca serena angelo assunta natale pasquale domenica primo secondo italia gemma flora
regina vera norma palmira candida franco libero leone romano clemente innocente modesto tosca
mercedes dolores rosario pilar carmen camille patrick mark frank will
""".split())
