"""插入模拟评论用于测试 UI 功能。运行完爬虫正式数据到位后可删除。"""
import asyncio, sys, uuid, random
from datetime import datetime, timedelta
sys.path.insert(0, 'backend')
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
from app.models import Comment

# 测试专用游戏 ID（固定值，与真实游戏隔离）
GAME_ID = uuid.UUID('aaaaaaaa-0000-0000-0000-000000000001')

SAMPLES = [
    ('steam_store','positive','praise','zh-cn','这款游戏真的太好玩了！背包系统设计得非常有创意，每次闯关都有新鲜感，强烈推荐！'),
    ('steam_store','negative','bug','zh-cn','游戏会随机崩溃，闯到第三层就闪退，存档也丢了，很让人沮丧。'),
    ('steam_store','positive','praise','zh-cn','策略深度超乎预期，背包组合玩法非常有趣，性价比极高！'),
    ('steam_store','negative','complaint','zh-cn','优化太差了，帧率不稳定，明明配置不低还是卡顿。'),
    ('steam_store','neutral','suggestion','zh-cn','建议增加多人联机模式，一个人玩久了有些单调。'),
    ('steam_store','positive','praise','en','Absolutely love this game! The backpack management mechanic is super creative and addictive.'),
    ('steam_store','negative','bug','en','Game crashes every time I reach floor 5. Really frustrating. Please fix ASAP.'),
    ('steam_store','neutral','suggestion','en','Would love to see more item variety in future updates. The current selection feels a bit limited.'),
    ('steam_store','positive','praise','en','One of the best roguelikes I have played this year. Highly recommended!'),
    ('steam_store','negative','complaint','en','The difficulty spike at floor 3 is way too harsh. Feels unbalanced and unfair.'),
    ('steam_store','positive','praise','zh-cn','关卡设计非常用心，Boss 战有挑战性但不至于让人抓狂，赞！'),
    ('steam_store','neutral','other','zh-cn','刚入手，还在摸索玩法，总体感觉还不错。'),
    ('steam_store','negative','bug','zh-cn','背包满了之后拖拽物品会卡住，导致操作失误，急需修复。'),
    ('steam_store','positive','praise','zh-tw','背包系統設計非常獨特，玩法有深度，值得入手！'),
    ('steam_store','negative','complaint','zh-cn','内容太少，20元的价格感觉不值，希望多出些新关卡。'),
    ('steam_hub','positive','suggestion','zh-cn','求开发者出个道具百科全书，很多道具效果不知道，每次都要自己试。'),
    ('steam_hub','negative','bug','zh-cn','遇到了一个严重 bug：使用某张卡牌后游戏直接卡死，只能强退。'),
    ('steam_hub','neutral','other','zh-cn','有没有大神分享一下通关攻略？第四层 Boss 我打了十几次了还是输。'),
    ('steam_hub','positive','praise','en','Just reached floor 10! The game gets really interesting after floor 5. Keep going!'),
    ('steam_hub','neutral','suggestion','en','Please add controller support. Would make the game much more comfortable to play.'),
    ('steam_hub','negative','complaint','en','Bought the game expecting more content. It feels incomplete. Where is the promised DLC?'),
    ('steam_hub','positive','other','ja','このゲームすごく面白い！バックパックの組み合わせが無限にあって何時間でも遊べる。'),
    ('steam_hub','negative','bug','ja','セーブデータが消えるバグがあります。早急に修正をお願いします。'),
    ('steam_hub','positive','praise','zh-cn','终于打过全成就了！这游戏值回票价，开发者辛苦了！'),
    ('steam_hub','neutral','suggestion','zh-cn','希望可以加入排行榜系统，这样和朋友比较分数会更有动力。'),
    ('steam_hub','negative','complaint','zh-cn','更新太慢了，上次大更新还是三个月前，希望开发组加快进度。'),
    ('steam_hub','positive','praise','en','The depth of strategy here is incredible. Every run feels different. 10/10!'),
    ('steam_hub','neutral','other','ko','이 게임 정말 재미있네요! 한국어 패치 언제 나오나요?'),
    ('steam_hub','negative','bug','zh-cn','多人对战匹配经常失败，等待十分钟都匹配不到人，服务器有问题吗？'),
    ('steam_hub','positive','suggestion','zh-cn','建议出个每日挑战模式，每天不同的随机种子，复玩性会更高！'),
    ('steam_store','positive','praise','zh-cn','美术风格非常可爱，音乐也很好听，是一款让人放松的小游戏。'),
    ('steam_store','negative','bug','en','Mouse cursor disappears after alt-tabbing. Have to restart the game to fix it.'),
    ('steam_store','positive','praise','en','Fantastic game for the price. Worth every penny. Will definitely recommend to friends.'),
    ('steam_store','neutral','suggestion','zh-cn','希望加入云存档功能，换电脑就得重新来过太麻烦了。'),
    ('steam_store','negative','complaint','zh-cn','游戏结局太仓促，明显没做完就上架了，有圈钱嫌疑。'),
    ('steam_hub','positive','praise','zh-cn','连续玩了 8 个小时，停不下来！这游戏真的上瘾。'),
    ('steam_hub','neutral','other','en','Is there any way to rebind keys? The default layout is a bit awkward for me.'),
    ('steam_hub','negative','bug','zh-cn','成就系统有 bug，达成条件了但成就没有解锁，希望修复。'),
    ('steam_hub','positive','suggestion','zh-cn','如果能加入 mod 支持就完美了，社区肯定会创作出很多有趣的内容。'),
    ('steam_store','positive','praise','zh-cn','国产独立游戏佳作！支持国内开发者，希望越做越好！'),
    ('steam_store','negative','complaint','en','The tutorial is too short and unclear. I had no idea what I was doing for the first hour.'),
    ('steam_hub','neutral','suggestion','zh-cn','希望可以跳过开场动画，每次重新进游戏都要等一遍有点烦。'),
    ('steam_hub','positive','praise','zh-tw','劇情設計很有深度，結局讓我出乎意料，值得細細品味。'),
    ('steam_store','negative','bug','zh-cn','背景音乐在某些情况下会突然消失，重进存档才恢复，求修复。'),
    ('steam_hub','positive','other','zh-cn','这游戏的隐藏结局真的震撼到我了，三周目才发现，开发者太用心了！'),
    ('steam_hub','neutral','suggestion','en','Add an in-game bestiary or item encyclopedia. It would help new players a lot.'),
    ('steam_store','negative','complaint','zh-cn','DLC 定价太高，和本体差不多的价格，内容量却少很多，不划算。'),
    ('steam_hub','positive','praise','zh-cn','每一局都不一样，随机性做得非常好，百玩不厌！'),
    ('steam_store','neutral','other','en','Decent game overall. Not revolutionary but solid and fun. Good for a lazy afternoon.'),
    ('steam_hub','negative','bug','en','Game freezes for 5 seconds every time I open the inventory. Happens consistently.'),
    ('steam_store','positive','praise','zh-cn','玩了整整一周，终于全成就了！开发团队非常用心，期待续作！'),
]

settings = get_settings()
engine = create_async_engine(settings.database_url)
factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def seed():
    random.seed(42)
    async with factory() as db:
        base_date = datetime.now()
        for i, (platform, sentiment, category, lang, content) in enumerate(SAMPLES):
            delta = timedelta(days=random.uniform(0, 30), hours=random.uniform(0, 24))
            pub_date = base_date - delta
            c = Comment(
                game_id=GAME_ID,
                platform=platform,
                source_type='review' if platform == 'steam_store' else 'discussion',
                author_name=f'测试用户_{i+1}',
                content=content,
                content_lang=lang,
                published_at=pub_date,
                fetched_at=datetime.now(),
                sentiment=sentiment,
                sentiment_score=round(random.uniform(0.6, 0.95), 2),
                category=category,
                is_duplicate=False,
            )
            db.add(c)
        await db.commit()
        print(f'已插入 {len(SAMPLES)} 条模拟评论，可刷新页面测试')

asyncio.run(seed())
