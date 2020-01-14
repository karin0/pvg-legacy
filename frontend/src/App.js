import React, { Component } from 'react';

import 'typeface-roboto';

import { AppBar, CssBaseline, Toolbar, Typography, Container, IconButton,
    TextField, Chip, Slide, Drawer, List, Divider, useScrollTrigger } from '@material-ui/core';

import { withStyles, ThemeProvider } from '@material-ui/core/styles';

import Autocomplete from '@material-ui/lab/Autocomplete';
import MenuIcon from '@material-ui/icons/Menu';

import ListboxComponent from './Listbox.js'
import PvgGallery from './PvgGallery.js'
import { host } from './env.js';
import theme from './theme.js';

import ListItem from '@material-ui/core/ListItem';
import ListItemIcon from '@material-ui/core/ListItemIcon';
import ListItemText from '@material-ui/core/ListItemText';

import Button from '@material-ui/core/Button';
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';

import UpdateIcon from '@material-ui/icons/Update';
import CloudDownloadIcon from '@material-ui/icons/CloudDownload';
import EcoIcon from '@material-ui/icons/Eco';
import DoneIcon from '@material-ui/icons/Done';
import SyncIcon from '@material-ui/icons/Sync';

function compare(a, b) {
    if (a < b)
        return -1;
    if (a > b)
        return 1;
    return 0;
}

function compare_fallback(a, b, fallback) {
    if (a < b)
        return -1;
    if (a > b)
        return 1;
    return fallback();
}

function HideOnScroll(props) {
    const { children, window } = props;
    const trigger = useScrollTrigger({ target: window ? window() : undefined });
  
    return (
      <Slide appear={false} direction="down" in={!trigger}>
        {children}
      </Slide>
    );
}

const styles = theme => ({
    list: {
        width: 270,
    },
    fullList: {
        width: 'auto',
    },

    menu_button: {
        marginRight: theme.spacing(2),
    },
    card: {
        paddingTop: theme.spacing(4),
        paddingBottom: theme.spacing(4),
    },
    box: {
        width: '100%',
        '& > * + *': {
            marginTop: theme.spacing(3),
        },
    },
    chip: {
        background: '#e3f2fd',
        color: '#1976d2'
    },
    clear_indicator: {
        color: 'white'
    },
    input: {
        color: 'white' 
    },
    input_root: {
        borderColor: 'white'
    }
});

function FullUpdateItem(props) {
    const [dialog_open, set_open] = React.useState(false);

    const open_dialog = () => {
        set_open(true);
    };

    const close_dialog = () => {
        set_open(false);
    };

    const confirm = () => {
        window.open(host + 'action/update');
        set_open(false);
        props.on_confirm();
    }

    return (
        <div>
            <ListItem button key="update" onClick={open_dialog}>
                <ListItemIcon>
                    <SyncIcon />
                </ListItemIcon>
                <ListItemText primary="Full Update" />
            </ListItem>
            <Dialog
                open={dialog_open}
                onClose={close_dialog}
                aria-labelledby="alert-dialog-title"
                aria-describedby="alert-dialog-description"
            >
                <DialogTitle id="alert-dialog-title">{"Warning"}</DialogTitle>
                <DialogContent>
                    <DialogContentText id="alert-dialog-description">
                        The operation may take a long time if excessive number of illusts are bookmarked. An incremental update is suggested in most cases.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                <Button onClick={confirm} variant="contained" color="secondary" disableElevation>
                    Continue
                </Button>
                <Button onClick={close_dialog} color="primary" autoFocus>
                    Cancel
                </Button>
                </DialogActions>
            </Dialog>
        </div>
    );
}

const action_mapper = cb => x => (
    <ListItem button key={x[2]} component="a" href={host + 'action/' + x[2]} target="_blank" onClick={cb}>
        <ListItemIcon>
            {x[1]}
        </ListItemIcon>
        <ListItemText primary={x[0]} />
    </ListItem>
);
const action_listitems_1 = [
    ['Incremental Update', <UpdateIcon />, 'qupd']
];
const action_listitems_2 = [
    ['Download All', <CloudDownloadIcon />, 'download'],
    ['Greendam', <EcoIcon />, 'greendam'],
    ['QUDG', <DoneIcon />, 'qudg']
];

class App extends Component {
    constructor(props) {
        super(props);
        this.state = {
            error: null,
            loaded: false,
            images: [],
            tags_list: [],
            tags_curr: [],
            locating_id: -1,
            drawer_open: false
        };
    }

    update() {
        console.log('update with', this.state.tags_curr, this.state.locating_id);
        fetch(host + 'select', {
            crossDomain: true,
            method: 'POST',
            body: JSON.stringify({
                filters: this.state.tags_curr
            }),
            headers: new Headers({
                'Content-Type': 'application/json'
            })
        })
        .then(res => res.json())
        .then(
            res => {
                let s = new Map();
                for (const img of res.items)
                    for (const tag of img.tags) {
                        const c = s.get(tag);
                        s.set(tag, c ? c + 1 : 1);
                    }
                s = Array.from(s[Symbol.iterator]());
                s.sort((a, b) => compare_fallback(b[1], a[1], () => compare(a[0], b[0])));

                this.setState({
                    loaded: true,
                    error: null,
                    images: res.items,
                    tags_list: s.map(a => a[0])
                });
            },
            error => {
                this.setState({
                    loaded: true,
                    error: error,
                    images: [],
                    tags_list: []
                });
            }
        );
    }
    set_tags = tags => {
        console.log('sets', tags);
        this.setState({
            tags_curr: tags,
            locating_id: -1
        }, this.update);
    };

    add_tag = (tag, id) => {
        console.log('add', tag);
        if (!this.state.tags_curr.includes(tag))
            this.setState(state => {
                return {
                    tags_curr: state.tags_curr.concat([tag]),
                    locating_id: id
                };
            }, this.update);
    };

    componentDidMount() {
        this.update();
    }

    render() {
        const { classes } = this.props;

        const open_drawer = () => this.setState({drawer_open: true});
        const close_drawer = () => this.setState({drawer_open: false});

        return (
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <HideOnScroll>
                    <AppBar position="fixed">
                        <Toolbar variant="dense">
                            <IconButton
                                edge="start"
                                className={classes.menu_button}
                                color="inherit"
                                onClick={open_drawer}
                            >
                                <MenuIcon />
                            </IconButton>
                            <div className={classes.box}>
                                <Autocomplete
                                    multiple
                                    freeSolo
                                    options={this.state.tags_list}
                                    ListboxComponent={ListboxComponent}
                                    renderTags={(value, getTagProps) =>
                                        value.map((option, index) => (
                                            <Chip
                                                classes={{root: classes.chip}}
                                                variant="outlined"
                                                color="primary"
                                                label={option}
                                                {...getTagProps({ index })}
                                            />
                                        ))
                                    }
                                    renderInput={params => (
                                        <TextField
                                            fullWidth
                                            color="primary"
                                            {...params}
                                        />
                                    )}
                                    onChange={ (e, value) => this.set_tags(value) }
                                    renderOption={option => <Typography noWrap>{option}</Typography>}
                                    value={this.state.tags_curr}
                                    classes={{
                                        clearIndicator: classes.clear_indicator,
                                        inputRoot: classes.input_root,
                                        input: classes.input
                                    }}
                                />
                            </div>
                        </Toolbar>
                    </AppBar>
                </HideOnScroll>
                <Drawer open={this.state.drawer_open} onClose={close_drawer}>
                    <div
                    className={classes.list}
                    role="presentation"
                    >
                    <List>
                        {action_listitems_1.map(action_mapper(close_drawer))}
                        <FullUpdateItem on_confirm={close_drawer} />
                        {action_listitems_2.map(action_mapper(close_drawer))}
                    </List>
                    <Divider />
                    </div>
                </Drawer>
                <Container className={classes.card} maxWidth="lg">
                    {this.state.loaded ?
                        (this.state.error ?
                            <div>
                                Error
                            </div> :
                            <PvgGallery
                                images={this.state.images}
                                locating_id={this.state.locating_id}
                                update_tags={this.add_tag}
                            />
                        ) :
                        <div>
                            Loading..
                        </div>
                    }
                </Container>
            </ThemeProvider>
        );
    }
}

export default withStyles(styles)(App);
