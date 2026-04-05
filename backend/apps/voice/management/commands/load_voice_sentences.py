"""
Management command: load_voice_sentences
Seeds the voice_sentences table with 5 training sentences per language.
Run once after first migration:
  python manage.py load_voice_sentences
  python manage.py load_voice_sentences --language ar  # seed one language only
"""

from django.core.management.base import BaseCommand
from apps.voice.models import VoiceSentence

SENTENCES = {
    "en": [
        "The quick brown fox jumps over the lazy dog near the riverbank.",
        "She sells seashells by the seashore every morning before sunrise.",
        "Technology is changing the way we communicate across the world.",
        "The weather today is perfect for a long walk in the park.",
        "I enjoy reading books and listening to music in my free time.",
    ],
    "ar": [
        "الثعلب البني السريع يقفز فوق الكلب الكسول بالقرب من النهر.",
        "التكنولوجيا تغير طريقة تواصلنا مع بعضنا البعض حول العالم.",
        "أستمتع بقراءة الكتب والاستماع إلى الموسيقى في وقت الفراغ.",
        "الطقس اليوم رائع للتنزه في الحديقة مع العائلة والأصدقاء.",
        "أتعلم لغات جديدة لأتواصل مع أشخاص من ثقافات مختلفة حول العالم.",
    ],
    "es": [
        "El veloz zorro marrón salta sobre el perro perezoso junto al río.",
        "La tecnología está cambiando la forma en que nos comunicamos en todo el mundo.",
        "Me gusta leer libros y escuchar música en mi tiempo libre.",
        "El tiempo hoy es perfecto para dar un largo paseo por el parque.",
        "Aprendo idiomas para comunicarme con personas de diferentes culturas.",
    ],
    "fr": [
        "Le rapide renard brun saute par-dessus le chien paresseux près de la rivière.",
        "La technologie change notre façon de communiquer dans le monde entier.",
        "J'aime lire des livres et écouter de la musique pendant mon temps libre.",
        "Le temps aujourd'hui est parfait pour une longue promenade dans le parc.",
        "J'apprends de nouvelles langues pour parler avec des personnes de cultures différentes.",
    ],
    "de": [
        "Der schnelle braune Fuchs springt über den faulen Hund am Flussufer.",
        "Technologie verändert die Art und Weise, wie wir miteinander kommunizieren.",
        "Ich lese gerne Bücher und höre Musik in meiner Freizeit.",
        "Das Wetter heute ist perfekt für einen langen Spaziergang im Park.",
        "Ich lerne neue Sprachen, um mit Menschen aus verschiedenen Kulturen zu kommunizieren.",
    ],
    "it": [
        "La rapida volpe marrone salta sopra il cane pigro vicino al fiume.",
        "La tecnologia sta cambiando il modo in cui comunichiamo in tutto il mondo.",
        "Mi piace leggere libri e ascoltare musica nel mio tempo libero.",
        "Il tempo oggi è perfetto per una lunga passeggiata nel parco.",
        "Imparo nuove lingue per comunicare con persone di culture diverse.",
    ],
    "pt": [
        "A rápida raposa marrom pula sobre o cão preguiçoso perto do rio.",
        "A tecnologia está mudando a forma como nos comunicamos em todo o mundo.",
        "Eu gosto de ler livros e ouvir música no meu tempo livre.",
        "O tempo hoje está perfeito para uma longa caminhada no parque.",
        "Aprendo idiomas para me comunicar com pessoas de diferentes culturas.",
    ],
    "pl": [
        "Szybki brązowy lis przeskakuje przez leniwego psa przy rzece.",
        "Technologia zmienia sposób, w jaki komunikujemy się na całym świecie.",
        "Lubię czytać książki i słuchać muzyki w wolnym czasie.",
        "Pogoda dzisiaj jest idealna na długi spacer po parku.",
        "Uczę się nowych języków, aby komunikować się z ludźmi z różnych kultur.",
    ],
    "tr": [
        "Hızlı kahverengi tilki, nehrin yanındaki tembel köpeğin üzerinden atladı.",
        "Teknoloji, dünya genelinde iletişim kurma biçimimizi değiştiriyor.",
        "Boş zamanlarımda kitap okumayı ve müzik dinlemeyi seviyorum.",
        "Bugün hava, parkta uzun bir yürüyüş için mükemmel.",
        "Farklı kültürlerden insanlarla iletişim kurmak için yeni diller öğreniyorum.",
    ],
    "ru": [
        "Быстрая коричневая лиса прыгает через ленивую собаку у реки.",
        "Технологии меняют то, как мы общаемся по всему миру.",
        "Я люблю читать книги и слушать музыку в свободное время.",
        "Сегодня погода идеальна для долгой прогулки в парке.",
        "Я учу новые языки, чтобы общаться с людьми из разных культур.",
    ],
    "nl": [
        "De snelle bruine vos springt over de luie hond bij de rivier.",
        "Technologie verandert de manier waarop we wereldwijd communiceren.",
        "Ik lees graag boeken en luister naar muziek in mijn vrije tijd.",
        "Het weer vandaag is perfect voor een lange wandeling in het park.",
        "Ik leer nieuwe talen om te communiceren met mensen uit verschillende culturen.",
    ],
    "cs": [
        "Rychlá hnědá liška skáče přes líného psa u řeky.",
        "Technologie mění způsob, jakým komunikujeme po celém světě.",
        "Rád čtu knihy a poslouchám hudbu ve volném čase.",
        "Dnešní počasí je ideální pro dlouhou procházku v parku.",
        "Učím se nové jazyky, abych mohl komunikovat s lidmi z různých kultur.",
    ],
    "zh": [
        "快速的棕色狐狸跳过了河边懒惰的狗。",
        "科技正在改变我们在全球交流的方式。",
        "我喜欢在空闲时间读书和听音乐。",
        "今天的天气非常适合在公园里散步。",
        "我学习新语言，以便与来自不同文化的人交流。",
    ],
    "ja": [
        "素早い茶色のキツネが川のそばでのんびりした犬を飛び越えました。",
        "テクノロジーは私たちが世界中でコミュニケーションする方法を変えています。",
        "私は自由な時間に本を読んだり音楽を聴いたりするのが好きです。",
        "今日の天気は公園での長い散歩に最適です。",
        "私は異なる文化の人々とコミュニケーションするために新しい言語を学んでいます。",
    ],
    "ko": [
        "빠른 갈색 여우가 강가에서 게으른 개를 뛰어넘었습니다.",
        "기술은 전 세계적으로 우리가 소통하는 방식을 변화시키고 있습니다.",
        "저는 여가 시간에 책을 읽고 음악을 듣는 것을 좋아합니다.",
        "오늘 날씨는 공원에서 오랫동안 산책하기에 완벽합니다.",
        "저는 다양한 문화의 사람들과 소통하기 위해 새로운 언어를 배우고 있습니다.",
    ],
    "hu": [
        "A gyors barna róka átugorja a lusta kutyát a folyóparton.",
        "A technológia megváltoztatja, ahogy a világ minden táján kommunikálunk.",
        "Szeretek könyveket olvasni és zenét hallgatni szabadidőmben.",
        "A mai idő tökéletes egy hosszú sétához a parkban.",
        "Új nyelveket tanulok, hogy különböző kultúrájú emberekkel kommunikálhassak.",
    ],
    "hi": [
        "तेज़ भूरी लोमड़ी नदी के पास आलसी कुत्ते के ऊपर से कूद गई।",
        "प्रौद्योगिकी दुनिया भर में हमारे संवाद करने के तरीके को बदल रही है।",
        "मुझे अपने खाली समय में किताबें पढ़ना और संगीत सुनना पसंद है।",
        "आज का मौसम पार्क में लंबी सैर के लिए बिल्कुल उपयुक्त है।",
        "मैं विभिन्न संस्कृतियों के लोगों से संवाद करने के लिए नई भाषाएं सीख रहा हूं।",
    ],
}


class Command(BaseCommand):
    help = "Seed voice training sentences for all supported languages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--language",
            type=str,
            default=None,
            help="Seed only this language code (e.g. --language ar). Default: all languages.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            default=False,
            help="Overwrite existing sentences. Default: skip existing.",
        )

    def handle(self, *args, **options):
        target_lang = options["language"]
        overwrite   = options["overwrite"]
        languages   = {target_lang: SENTENCES[target_lang]} if target_lang else SENTENCES

        if target_lang and target_lang not in SENTENCES:
            self.stderr.write(self.style.ERROR(f"Language '{target_lang}' not found. Available: {', '.join(SENTENCES.keys())}"))
            return

        created_total = 0
        updated_total = 0

        for lang, sentences in languages.items():
            for position, sentence_text in enumerate(sentences, start=1):
                if overwrite:
                    _, created = VoiceSentence.objects.update_or_create(
                        language = lang,
                        position = position,
                        defaults = {"sentence": sentence_text},
                    )
                    if created:
                        created_total += 1
                    else:
                        updated_total += 1
                else:
                    _, created = VoiceSentence.objects.get_or_create(
                        language = lang,
                        position = position,
                        defaults = {"sentence": sentence_text},
                    )
                    if created:
                        created_total += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created: {created_total}, Updated: {updated_total}, "
            f"Languages seeded: {len(languages)}."
        ))
