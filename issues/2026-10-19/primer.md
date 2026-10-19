# Day 1 · A Model Is a File

*SI Primer · Monday, October 19, 2026*

Let's start simple, with the thing itself.

An AI model is a file.

That's it. A big file, sure. But a file. You can copy it. You can download it. You can put it on a drive and hand it to a friend, if your friend has a lot of room.

What's inside is numbers. Billions of them. Each one is called a *parameter*, a little dial that got nudged, a tiny bit at a time, while the model read an enormous pile of text. For Beam, below, that was 23.8 trillion tokens, roughly word-pieces. [Reflection](https://www.reflection.ai/blog/introducing-beam) Nobody set the dials by hand. They got set by learning. That's the strange part, and it's worth sitting with for a minute. Nobody programmed the intelligence. It grew into the numbers.

Here's this week's example. On October 16, a US lab called Reflection released a model called Beam on Hugging Face. It has 501 billion parameters. At full precision the file is about one terabyte. Squeezed down to 4 bits per number, it's about 280 gigabytes. [Hugging Face](https://huggingface.co/blog/reflection-beam)

A day earlier, Meta put out Muse Spark Open. 816 billion parameters. About 1.65 terabytes. [Meta](https://research.meta.ai/blog/muse-spark-open); [Meta docs](https://dev.meta.ai/docs/muse-spark-open/get-the-model)

So a frontier-grade brain now fits on a stack of hard drives that'd sit easy on a bookshelf.

Two things follow, and they pull in opposite directions.

**One. The file is cheap to copy.** Once it's out, it's out. Anybody with the hardware can run it. That's why prices fall when good open models show up. Bank of America says average token prices are down about half since summer. [Investing.com](https://www.investing.com/news/stock-market-news/can-ai-avoid-the-boomandbust-fate-of-past-capital-cycles-bofa-weighs-in-4953613)

**Two. The file is expensive to make.** Reflection says it ran 10,500 Nvidia GB300 GPUs for four weeks for just one stage of training, the reinforcement-learning run. [Reflection](https://www.reflection.ai/blog/introducing-beam) The copy costs pennies. The original costs a fortune.

And a file doesn't do anything sitting on a shelf. To answer a question, it has to be loaded onto chips, fed electricity and cooled. Every time. That's where the money shows up next. It's tomorrow's lesson.

## Why it matters for investors

When someone says an AI company is worth a trillion dollars, ask the simple question. *Is the value in the file, or around it?*

The file can leak, get matched or get given away. What's harder to copy is what surrounds it: the compute to make the next one, the power to run it, the customers who use it by default, and the trust that keeps them there.

Anthropic is expected to file publicly for its IPO next week, according to IFR. [IFR](https://www.ifre.com/equities/2499407/anthropic-pushes-ahead-with-mid-november-ipo) Keep that question in your pocket when the prospectus lands. Check whether the moat is the model, or everything around the model.

Copies are cheap. Making the next one isn't.

*Tomorrow: training vs. inference, the difference between building a brain and renting one out.*
