import React, { useState } from 'react';
import {
    Box, Button, TextField, Dialog, DialogActions,
    DialogContent, DialogTitle,
    Grid, RadioGroup, Radio,
    FormControl, FormLabel, FormControlLabel, Typography
} from '@material-ui/core';
import { host } from './env.js';

const noise_levels = [
    ['0', 'None'], ['1', 'Low'], ['2', 'Medium'], ['3', 'High'], ['4', 'Highest']
];

export default function UpscalingDialog(props) {
    const img = props.img;
    const default_noise_level =
        (img && (img.fn.substring(img.fn.length - 4) === '.jpg' || img.fn.substring(img.fn.length - 5) === '.jpeg')) ? "1" : "0";

    let default_old_w, default_old_h;
    if (img) {
        default_old_w = img.w;
        default_old_h = img.h;
    }

    const [file, set_file] = useState();

    const [old_wh, set_old_wh] = useState([default_old_w, default_old_h]);
    const [old_w, old_h] = old_wh;

    let default_ratio = '2.00';
    if (old_w) {
        let r = 2, x = Math.min(old_w, old_h) * 2;
        while (x <= 2340) {
            r *= 2;
            x *= 2;
        }
        default_ratio = r.toFixed(2);
    }

    const [ratio, set_ratio] = useState(default_ratio);

    console.log(img, old_w, old_h, ratio, file);
    return (
        <Dialog
            open={props.open}
            onClose={props.on_close}
            maxWidth="sm"
        >
            <form
                action={host + "upscale"}
                method="POST"
                target="_blank"
            >
                <DialogTitle>Upscaling</DialogTitle>
                <DialogContent>
                    <Box mb={2}>
                        {img ?
                            <>
                                <Typography>
                                    {`${img.title} - ${img.ind} (${img.fn}, ${img.w} x ${img.h})`}
                                </Typography>
                                <input name="pid" value={img.pid} style={{ display: "none" }} readOnly />
                                <input name="ind" value={img.ind} style={{ display: "none" }} readOnly />
                            </> :
                            <Grid container>
                                {file ?
                                    <Grid item>
                                        <Typography align="center" style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            justifyContent: "center"
                                        }}>
                                            {`${file.name} (${old_w} x ${old_h})`}
                                        </Typography>
                                    </Grid>
                                : null}
                                <Button
                                    variant="contained"
                                    component="label"
                                >
                                    Upload
                                    <input
                                        name="file"
                                        type="file"
                                        style={{ display: "none" }}
                                        onChange={e => {
                                            if (e.target.files) {
                                                const fp = e.target.files[0];
                                                set_file(fp);

                                                const im = new Image();
                                                im.src = window.URL.createObjectURL(fp);

                                                im.onload = () => {
                                                    set_old_wh([im.width, im.height]);
                                                    window.URL.revokeObjectURL(im.src);
                                                };
                                            }
                                        }}
                                    />
                                </Button>
                            </Grid>
                        }
                    </Box>
                    <FormControl component="fieldset" variant="outlined">
                        <FormLabel component="legend" style={{ fontSize: '1em' }}>Noise Reduction</FormLabel>
                        <RadioGroup name="noise-level" defaultValue={default_noise_level}>
                            <Grid container>
                            {noise_levels.map(opt =>
                                <Grid item>
                                    <FormControlLabel
                                        value={opt[0]}
                                        label={opt[1]}
                                        control={<Radio />}
                                    />
                                </Grid>
                            )}
                            </Grid>
                        </RadioGroup>
                    </FormControl>
                    <Box mt={1}>
                        <TextField
                            name="ratio"
                            margin="dense"
                            label="Scale Ratio"
                            type="number"
                            value={ratio}
                            inputProps={{ step: 0.01 }}
                            onChange={e => set_ratio(e.target.value)}
                            fullWidth
                        />
                    </Box>
                    <Box mt={1}>
                        <Grid container justify="space-between">
                            <Grid item>
                                <TextField
                                    margin="dense"
                                    label="Target Width"
                                    value={old_w ? Math.round(old_w * ratio) : "N/A"}
                                    disabled
                                    fullWidth
                                />
                            </Grid>
                            <Grid item>
                                <TextField
                                    margin="dense"
                                    label="Target Height"
                                    value={old_h ? Math.round(old_h * ratio) : "N/A"}
                                    disabled
                                    fullWidth
                                />
                            </Grid>
                        </Grid>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={props.on_close} color="primary">
                        Cancel
                    </Button>
                    <Button color="primary" type="submit">
                        Convert
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
}
