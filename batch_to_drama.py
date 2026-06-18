#!/usr/bin/env python3
"""
Convert 乐育堂语录 modern-life stories to TTS broadcast drama format.
Reads .md files from 乐育堂语录/, converts section 四 to drama script,
writes to 乐育堂语录_广播剧/.
"""
import re
import os
import glob

INPUT_DIR = '乐育堂语录'
OUTPUT_DIR = '乐育堂语录_广播剧'

FALSE_POSITIVES = {
    '轻声', '对她', '对他', '对他俩', '笑着', '看着', '拿着', '做着',
    '走着', '想着', '觉得', '说着', '那么', '什么', '怎么', '这样',
    '那样', '这个', '那个', '这些', '那些', '这里', '那里', '不停',
    '突然', '终于', '然后', '接着', '后来', '现在', '当时', '以前',
    '之后', '回头', '转身', '抬头', '低头', '开口', '闭口', '随口',
    '大声', '小声', '悄悄', '喃喃', '反复', '认真', '严肃', '开玩笑',
    '继续', '安慰', '解释', '补充', '强调', '感叹', '夸奖', '赞叹',
    '直接', '间接', '好奇', '疑惑', '惊讶', '惊喜', '慌忙', '赶紧',
    '可能', '一样', '已经', '就是', '还是', '真是', '不是', '没有',
    '知道', '觉得', '应该', '可以', '自己', '他们', '你们', '我们',
    '别人',
}

ROLE_NAMES = {
    '父亲', '妈妈', '母亲', '爸爸', '妻子', '老公', '爱人', '儿子',
    '女儿', '爷爷', '奶奶', '外婆', '外公', '姥姥', '姥爷',
    '同事', '朋友', '导师', '老师', '老板', '经理', '主任', '主管',
    '医生', '护士', '学生', '同学', '徒弟', '师父', '师傅',
    '邻居', '下属', '助理', '秘书', '老婆', '丈夫', '儿媳', '女婿',
    '侄子', '侄女', '孙子', '孙女', '舅舅', '舅妈', '姑姑', '姑父',
    '阿姨', '叔叔', '伯伯', '婶婶', '哥哥', '弟弟', '姐姐', '妹妹',
    '客户', '甲方', '乙方', '老伴', '女朋友',
}

FEMALE_ROLES = {
    '妻子', '妈妈', '母亲', '奶奶', '外婆', '姥姥', '阿姨', '婶婶',
    '姐姐', '妹妹', '女儿', '孙女', '侄女', '老婆', '爱人', '儿媳',
    '舅妈', '姑姑', '女士', '小姐', '夫人', '太太', '女朋友', '老伴',
    '婆婆',
}

ELDERLY_FEMALE = {'奶奶', '婆婆', '姥姥', '外婆', '老太太', '阿婆'}
ELDERLY_MALE = {'爷爷', '公公', '姥爷', '太爷', '老太爷'}
YOUNG_KW = {'小', '年轻', '青年', '少年', '同学', '学生'}
CHILD_KW = {'小朋友', '小孩', '孩子', '儿童', '宝宝', '娃娃'}

SURNAMES = set(
    '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张'
    '孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎'
    '鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤'
    '滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄'
    '穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞'
    '熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜'
    '郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管'
    '卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔'
    '吉钮龚程嵇邢滑裴陆荣翁'
)

Q_RE = re.compile(r'[\u201c\u201d"]([^\u201c\u201d"]*)[\u201c\u201d"]')


def re_match(pat, text):
    """Like re.search but with a leading boundary check via non-capturing group."""
    return re.search(r'(?:^|[^\u4e00-\u9fff])' + pat, text)


def re_finditer(pat, text):
    """Like re.finditer but with a leading boundary check."""
    return re.finditer(r'(?:^|[^\u4e00-\u9fff])' + pat, text)


def get_voice(char):
    if char == '旁白':
        return 'edge-tts:zh-CN-XiaoxiaoNeural'
    if any(kw in char for kw in CHILD_KW):
        return 'edge-tts:liaoning-XiaobeiNeural'
    if any(kw in char for kw in ELDERLY_FEMALE):
        return 'edge-tts:zh-CN-YunjianNeural'
    if any(kw in char for kw in ELDERLY_MALE):
        return 'edge-tts:zh-CN-YunjianNeural'
    if any(kw in char for kw in FEMALE_ROLES):
        return 'edge-tts:zh-CN-XiaoyiNeural'
    if any(kw in char for kw in YOUNG_KW):
        return 'edge-tts:zh-CN-YunyangNeural'
    if len(char) <= 3 and char[0] in ('老', '大', '阿'):
        return 'edge-tts:zh-CN-YunxiNeural'
    if char[0] in SURNAMES:
        return 'edge-tts:zh-CN-YunxiNeural'
    return 'edge-tts:zh-CN-YunxiNeural'


def split_sections(text):
    lines = text.split('\n')
    sections = []
    cur_h = None
    cur_b = []
    for line in lines:
        if line.startswith('## '):
            if cur_h is not None:
                sections.append((cur_h, cur_b))
            cur_h = line
            cur_b = []
        else:
            cur_b.append(line)
    if cur_h is not None:
        sections.append((cur_h, cur_b))
    return sections


def extract_protagonist(text):
    first_para = text.strip().split('\n\n')[0] if '\n\n' in text else text.strip()
    # Pattern: Name + 今年/现年/已经/是/是位/是一位/是一名
    for pat_str in [
        r'([\u4e00-\u9fff]{2,4})(?:今年|现年|已经|是位|是一位|是一名|是)',
    ]:
        m = re_match(pat_str, first_para)
        if m:
            name = m.group(1).strip()
            if name not in FALSE_POSITIVES and len(name) >= 2:
                return name
    # Pattern: Name + age digits + 岁 (e.g. 林远航三十五岁)
    m2 = re_match(r'([\u4e00-\u9fff]{2,3})[零一二三四五六七八九十百千万\d]{1,8}岁', first_para)
    if m2:
        name = m2.group(1)
        if name not in FALSE_POSITIVES and len(name) >= 2:
            if name[0] in SURNAMES or (len(name) <= 3 and name[0] in '老小阿'):
                return name
    # Pattern: first 2-3 chars followed by comma
    m3 = re.match(r'^\s*([\u4e00-\u9fff]{2,3})[，,]', first_para)
    if m3:
        name = m3.group(1).strip()
        if name not in FALSE_POSITIVES:
            return name
    return None


def is_valid_name(name):
    if len(name) < 2 or len(name) > 4:
        return False
    if name in FALSE_POSITIVES:
        return False
    if name in ROLE_NAMES:
        return True
    if name[0] in SURNAMES:
        return True
    if re.match(r'^[老小阿][\u4e00-\u9fff]{1,2}$', name):
        return True
    return False


def extract_characters(text):
    chars = set()
    for role in ROLE_NAMES:
        if role in text:
            chars.add(role)
    prot = extract_protagonist(text)
    if prot:
        chars.add(prot)
    for verb in ['说', '道', '问', '回答']:
        for m in re_finditer(rf'([\u4e00-\u9fff]{{2,4}}){verb}[：:]', text):
            name = m.group(1)
            if is_valid_name(name):
                chars.add(name)
    for m in re.finditer(r'对([\u4e00-\u9fff]{2,4})说[：:]', text):
        name = m.group(1)
        if is_valid_name(name):
            chars.add(name)
    for m in re.finditer(r'告诉([\u4e00-\u9fff]{2,4})[：:]', text):
        name = m.group(1)
        if is_valid_name(name):
            chars.add(name)
    return list(chars)


def find_speaker(pre_text, known_chars):
    t = pre_text.strip().rstrip('，。！？；、 \t')
    if not t:
        return None, pre_text

    # Check for NAME+colon/verb patterns at the end first (保留：:)
    for verb in ['说', '道', '问', '回答']:
        m = re.search(rf'([\u4e00-\u9fff]{{2,4}}){verb}[：:]?\s*$', t)
        if m:
            name = m.group(1)
            if name in known_chars:
                remaining = t[:m.start()].strip().strip('，、')
                return name, remaining

    m = re.search(r'([\u4e00-\u9fff]{2,4})[：:]\s*$', t)
    if m:
        name = m.group(1)
        if name in known_chars:
            remaining = t[:m.start()].strip().strip('，、')
            return name, remaining

    # Walk backward from end looking for NAME + action_text + colon/verb
    for char in sorted(known_chars, key=len, reverse=True):
        idx = t.rfind(char)
        if idx < 0:
            continue
        before_name = t[:idx].strip().strip('，、')
        after_name = t[idx + len(char):]

        if not after_name.strip():
            return char, before_name

        # If after_name contains another known character, this is probably
        # not the speaker (the other character is more relevant)
        has_other = False
        for c2 in known_chars:
            if c2 != char and c2 in after_name:
                has_other = True
                break
        if has_other:
            continue

        # Check for speech indicators after the name (including trailing colon)
        if re.search(r'(?:说[：:]?|道[：:]?|问[：:]?|回答[：:]?|[：:])', after_name):
            vm = re.search(r'(?:说[：:]?|道[：:]?|问[：:]?|回答[：:]?|[：:])', after_name)
            action_text = after_name[:vm.start()].strip()
            if action_text:
                combined = f'{before_name} {action_text}'.strip() if before_name else action_text
            else:
                combined = before_name
            return char, combined

    return None, pre_text


def has_dialogue(text):
    return bool(Q_RE.search(text))


def convert_section_to_drama(text):
    text = text.strip()
    if not text:
        return ''

    chars = extract_characters(text)
    if not chars:
        prot = extract_protagonist(text)
        if prot:
            chars = [prot]
        else:
            chars = ['主角']

    known_chars = set(chars)
    has_quotes = has_dialogue(text)
    drama = []

    if not has_quotes:
        for para in re.split(r'\n\s*\n', text):
            para = para.strip()
            if para:
                drama.append(f'[旁白] {para}')
    else:
        last_speaker = None
        for para in re.split(r'\n\s*\n', text):
            para = para.strip()
            if not para:
                continue

            quotes = list(Q_RE.finditer(para))
            if not quotes:
                drama.append(f'[旁白] {para}')
                continue

            pos = 0
            for q in quotes:
                pre = para[pos:q.start()]
                if pre:
                    speaker, remaining = find_speaker(pre, known_chars)
                    if speaker:
                        if speaker not in known_chars:
                            known_chars.add(speaker)
                            chars.append(speaker)
                        last_speaker = speaker
                        if remaining:
                            drama.append(f'[旁白] {remaining}')
                    else:
                        pc = pre.strip().strip('，。！？；、：: \t')
                        if pc:
                            drama.append(f'[旁白] {pc}')

                qt = q.group(1)
                # Check for post-quote speaker attribution
                after_para = para[q.end():].strip()
                post_attributed = None
                if after_para:
                    for ac in sorted(known_chars, key=len, reverse=True):
                        if after_para.startswith(ac):
                            post_attributed = ac
                            break
                # If this paragraph is a bare quote (no pre-text and nothing after),
                # default to protagonist rather than carry-over last speaker
                if post_attributed:
                    speaker = post_attributed
                else:
                    para_is_bare_quote = (not pre and not after_para)
                    if para_is_bare_quote:
                        speaker = '主角'
                    else:
                        speaker = last_speaker or '主角'
                drama.append(f'[{speaker}] {qt}')
                last_speaker = speaker
                pos = q.end()

            after = para[pos:].strip()
            if after:
                ac = after.strip('，。！？；、：: \t\n\r')
                if ac:
                    drama.append(f'[旁白] {ac}')

    all_chars = ['旁白'] + [c for c in chars if c != '旁白']
    seen = set()
    vlines = ['**【角色与声音映射】**']
    for c in all_chars:
        if c not in seen:
            seen.add(c)
            vlines.append(f'- {c} = {get_voice(c)}')

    result = '\n'.join(vlines) + '\n\n**【脚本】**'
    if drama:
        result += '\n' + '\n'.join(drama)
    return result


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = split_sections(content)
    if not sections:
        return content

    out = []
    found = False
    for heading, body in sections:
        h = heading.strip()
        bt = '\n'.join(body).strip()

        if '四、现代生活' in h:
            drama = convert_section_to_drama(bt)
            out.append('## 四、广播剧脚本')
            out.append('')
            out.append(drama)
            found = True
        else:
            out.append(h)
            out.append('')
            if bt:
                out.append(bt)
                out.append('')

    if not found:
        return content

    result = '\n'.join(out)
    if not result.endswith('\n'):
        result += '\n'
    return result


def check_dialogue_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    for heading, body in split_sections(content):
        if '四、现代生活' in heading:
            return has_dialogue('\n'.join(body))
    return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(glob.glob(os.path.join(INPUT_DIR, '*.md')))
    files = [f for f in files if 'README.md' not in os.path.basename(f)]

    stats = {'total': 0, 'with_dialogue': 0, 'narration_only': 0, 'errors': []}

    for fp in files:
        fname = os.path.basename(fp)
        try:
            output = process_file(fp)
            with open(os.path.join(OUTPUT_DIR, fname), 'w', encoding='utf-8') as f:
                f.write(output)

            if check_dialogue_in_file(fp):
                stats['with_dialogue'] += 1
            else:
                stats['narration_only'] += 1

            stats['total'] += 1
            print(f'  ✓ {fname}')

        except Exception as e:
            stats['errors'].append(f'{fname}: {e}')
            stats['total'] += 1
            print(f'  ✗ {fname} - ERROR: {e}')

    print(f'\n{"="*50}')
    print(f'Total: {stats["total"]}')
    print(f'  With dialogue: {stats["with_dialogue"]}')
    print(f'  Narration-only: {stats["narration_only"]}')
    print(f'  Errors: {len(stats["errors"])}')
    for e in stats['errors']:
        print(f'    - {e}')

    samples = ['解读_卷一第一条.md', '解读_卷二第1条.md', '解读_卷二第10条.md']
    print(f'\n{"="*50}')
    print('SAMPLES (广播剧 script):')
    for fname in samples:
        p = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                c = f.read()
            m = re.search(r'## 四、广播剧脚本\n(.*)', c, re.DOTALL)
            preview = m.group(1).strip()[:800] if m else '  (not found)'
            print(f'\n--- {fname} ---')
            print(preview)
            print('...')


if __name__ == '__main__':
    main()
