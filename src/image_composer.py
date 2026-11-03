from PIL import Image

def combine_banner_and_chart(banner_path, chart_path, output_path="combined_signal.png"):
    try:
        banner = Image.open(banner_path)
        chart = Image.open(chart_path)

        # Resize banner to match chart width
        chart_width = chart.width
        banner = banner.resize((chart_width, int(banner.height * (chart_width / banner.width))))

        # Create combined image
        total_height = banner.height + chart.height
        combined = Image.new('RGB', (chart_width, total_height), (255, 255, 255))

        combined.paste(banner, (0, 0))
        combined.paste(chart, (0, banner.height))

        combined.save(output_path)
        return output_path
    except Exception as e:
        print(f"Image combination error: {e}")
        return None
