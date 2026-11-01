const express = require('express');
const app = express();
app.use(express.json());

// जब भी ऐप लाइसेंस या की चेक करेगी
app.post('/api/license/verify-android', (req, res) => {
    res.json({
        success: true,
        message: "Key ekdum valid hai!",
        entitlement: "licensed",
        tier: "promax"
    });
});

app.post('/api/android/bootstrap', (req, res) => {
    res.json({
        ok: true,
        entitlement: "licensed",
        tier: "promax",
        pricing: {},
        config: {}
    });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
