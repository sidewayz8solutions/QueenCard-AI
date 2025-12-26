-- LoRA models table
CREATE TABLE IF NOT EXISTS loras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    preview_url TEXT,
    r2_key TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    tags JSONB DEFAULT '[]'::jsonb,
    trigger_words JSONB DEFAULT '[]'::jsonb,
    base_model TEXT DEFAULT 'sd15',
    is_nsfw BOOLEAN DEFAULT false,
    is_public BOOLEAN DEFAULT true,
    owner_id UUID REFERENCES auth.users(id),
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Base models table
CREATE TABLE IF NOT EXISTS base_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    preview_url TEXT,
    hf_repo TEXT NOT NULL,
    model_type TEXT DEFAULT 'sd15' CHECK (model_type IN ('sd15', 'sdxl', 'svd', 'animatediff')),
    is_nsfw BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Training jobs table
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    training_type TEXT NOT NULL CHECK (training_type IN ('lora', 'dreambooth')),
    base_model TEXT NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    input_images JSONB DEFAULT '[]'::jsonb,
    output_lora_id UUID REFERENCES loras(id),
    error TEXT,
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_loras_category ON loras(category);
CREATE INDEX IF NOT EXISTS idx_loras_is_nsfw ON loras(is_nsfw);
CREATE INDEX IF NOT EXISTS idx_loras_slug ON loras(slug);
CREATE INDEX IF NOT EXISTS idx_training_jobs_user_id ON training_jobs(user_id);

-- RLS for loras
ALTER TABLE loras ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public loras visible to all" ON loras FOR SELECT USING (is_public = true);
CREATE POLICY "Owners can manage own loras" ON loras FOR ALL USING (owner_id = auth.uid());
CREATE POLICY "Service role full access loras" ON loras FOR ALL USING (auth.role() = 'service_role');

-- RLS for training_jobs
ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own training jobs" ON training_jobs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create training jobs" ON training_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Service role full access training" ON training_jobs FOR ALL USING (auth.role() = 'service_role');

-- Update jobs table to support video
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_type TEXT DEFAULT 'img2img' CHECK (job_type IN ('img2img', 'img2vid', 'txt2img', 'txt2vid'));
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS video_params JSONB DEFAULT '{}'::jsonb;

-- Seed some base models
INSERT INTO base_models (name, slug, hf_repo, model_type, is_nsfw, description) VALUES
('Realistic Vision V5', 'realistic-vision-v5', 'SG161222/Realistic_Vision_V5.1_noVAE', 'sd15', true, 'Photorealistic model'),
('DreamShaper 8', 'dreamshaper-8', 'Lykon/DreamShaper', 'sd15', false, 'Versatile artistic model'),
('SDXL Base', 'sdxl-base', 'stabilityai/stable-diffusion-xl-base-1.0', 'sdxl', false, 'Stable Diffusion XL'),
('Stable Video Diffusion', 'svd', 'stabilityai/stable-video-diffusion-img2vid-xt', 'svd', false, 'Image to video generation')
ON CONFLICT (slug) DO NOTHING;

-- Seed NSFW LoRAs
INSERT INTO loras (name, slug, description, r2_key, category, tags, trigger_words, base_model, is_nsfw, is_public) VALUES
-- Effects
('Cumshot', 'cumshot', 'Realistic cumshot effect LoRA', 'loras/cumshot.safetensors', 'effect', '["effect", "nsfw", "realistic"]', '["cumshot", "cum on face", "cum on body"]', 'sd15', true, true),
('Facial', 'facial', 'Facial effect LoRA', 'loras/facial.safetensors', 'effect', '["effect", "nsfw"]', '["facial", "messy"]', 'sd15', true, true),
('Ahegao', 'ahegao', 'Ahegao expression LoRA', 'loras/ahegao.safetensors', 'expression', '["expression", "face", "nsfw"]', '["ahegao", "tongue out", "rolling eyes"]', 'sd15', true, true),

-- Poses
('Doggystyle', 'doggystyle', 'Doggystyle pose LoRA', 'loras/doggystyle.safetensors', 'pose', '["pose", "nsfw", "position"]', '["doggystyle", "from behind"]', 'sd15', true, true),
('Missionary', 'missionary', 'Missionary pose LoRA', 'loras/missionary.safetensors', 'pose', '["pose", "nsfw", "position"]', '["missionary", "lying down"]', 'sd15', true, true),
('Cowgirl', 'cowgirl', 'Cowgirl pose LoRA', 'loras/cowgirl.safetensors', 'pose', '["pose", "nsfw", "position"]', '["cowgirl", "riding", "on top"]', 'sd15', true, true),
('Blowjob', 'blowjob', 'Blowjob pose LoRA', 'loras/blowjob.safetensors', 'pose', '["pose", "nsfw", "oral"]', '["blowjob", "oral", "sucking"]', 'sd15', true, true),
('Spread Legs', 'spread-legs', 'Spread legs pose LoRA', 'loras/spread-legs.safetensors', 'pose', '["pose", "nsfw"]', '["spread legs", "spreading"]', 'sd15', true, true),

-- Body types
('Big Breasts', 'big-breasts', 'Large breasts enhancement', 'loras/big-breasts.safetensors', 'body', '["body", "breasts", "nsfw"]', '["big breasts", "large breasts", "huge breasts"]', 'sd15', true, true),
('Big Ass', 'big-ass', 'Large posterior enhancement', 'loras/big-ass.safetensors', 'body', '["body", "ass", "nsfw"]', '["big ass", "large ass", "thicc"]', 'sd15', true, true),
('Petite', 'petite', 'Petite body type', 'loras/petite.safetensors', 'body', '["body", "petite", "nsfw"]', '["petite", "small body", "slim"]', 'sd15', true, true),
('Muscular Female', 'muscular-female', 'Muscular female body', 'loras/muscular-female.safetensors', 'body', '["body", "muscular", "nsfw"]', '["muscular", "fit", "abs"]', 'sd15', true, true),

-- Clothing/Outfits
('Lingerie', 'lingerie', 'Sexy lingerie LoRA', 'loras/lingerie.safetensors', 'clothing', '["clothing", "lingerie", "nsfw"]', '["lingerie", "lace", "bra and panties"]', 'sd15', true, true),
('Bikini', 'bikini', 'Bikini and swimwear', 'loras/bikini.safetensors', 'clothing', '["clothing", "swimwear", "nsfw"]', '["bikini", "swimsuit", "beach"]', 'sd15', true, true),
('Latex', 'latex', 'Latex and rubber clothing', 'loras/latex.safetensors', 'clothing', '["clothing", "latex", "fetish"]', '["latex", "rubber", "shiny"]', 'sd15', true, true),
('Maid Outfit', 'maid-outfit', 'Sexy maid costume', 'loras/maid-outfit.safetensors', 'clothing', '["clothing", "costume", "nsfw"]', '["maid", "maid outfit", "french maid"]', 'sd15', true, true),
('Schoolgirl', 'schoolgirl', 'Schoolgirl uniform', 'loras/schoolgirl.safetensors', 'clothing', '["clothing", "uniform", "nsfw"]', '["schoolgirl", "school uniform", "plaid skirt"]', 'sd15', true, true),
('Nurse', 'nurse', 'Sexy nurse costume', 'loras/nurse.safetensors', 'clothing', '["clothing", "costume", "nsfw"]', '["nurse", "nurse outfit", "medical"]', 'sd15', true, true),

-- Styles
('Hentai Style', 'hentai-style', 'Anime hentai art style', 'loras/hentai-style.safetensors', 'style', '["style", "anime", "hentai"]', '["hentai", "anime style", "2d"]', 'sd15', true, true),
('Realistic Skin', 'realistic-skin', 'Enhanced realistic skin texture', 'loras/realistic-skin.safetensors', 'style', '["style", "realistic", "skin"]', '["realistic skin", "detailed skin", "pores"]', 'sd15', true, true),
('Oiled Body', 'oiled-body', 'Oily/wet skin effect', 'loras/oiled-body.safetensors', 'style', '["style", "wet", "oil"]', '["oiled", "wet", "shiny skin", "glistening"]', 'sd15', true, true),

-- Fetish
('Bondage', 'bondage', 'BDSM and bondage elements', 'loras/bondage.safetensors', 'fetish', '["fetish", "bdsm", "bondage"]', '["bondage", "tied up", "rope", "handcuffs"]', 'sd15', true, true),
('Feet', 'feet', 'Foot fetish LoRA', 'loras/feet.safetensors', 'fetish', '["fetish", "feet"]', '["feet", "toes", "soles", "barefoot"]', 'sd15', true, true),
('Gangbang', 'gangbang', 'Multiple partners scene', 'loras/gangbang.safetensors', 'fetish', '["fetish", "group", "nsfw"]', '["gangbang", "group", "multiple"]', 'sd15', true, true)

ON CONFLICT (slug) DO NOTHING;

