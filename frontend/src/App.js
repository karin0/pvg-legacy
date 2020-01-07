import React, { Component } from 'react';

import 'typeface-roboto';

import AppBar from '@material-ui/core/AppBar';
import CssBaseline from '@material-ui/core/CssBaseline';
import Toolbar from '@material-ui/core/Toolbar';
import Typography from '@material-ui/core/Typography';
import Container from '@material-ui/core/Container';
import IconButton from '@material-ui/core/IconButton';
import TextField from '@material-ui/core/TextField';
import Chip from '@material-ui/core/Chip';
import { withStyles, ThemeProvider } from '@material-ui/core/styles';

import Autocomplete from '@material-ui/lab/Autocomplete';
import MenuIcon from '@material-ui/icons/Menu';

import ListboxComponent from './Listbox.js'
import PvgGallery from './PvgGallery.js'
import { host } from './env.js';
import theme from './theme.js';

const styles = theme => ({
    menuButton: {
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
    }
});

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

class App extends Component {
    constructor(props) {
        super(props);
        this.state = {
            error: null,
            loaded: false,
            images: [],
            tags_list: [],
            tags_curr: [],
            locating_id: -1
        };
    }

    update() {
        console.log('update with', this.state.tags_curr);
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

    /*
    resize() {
        this.setState({});
    }
    componentDidMount() {
        window.addEventListener('resize', this.resize);
    }
    componentWillUnmount() {
        window.removeEventListener('resize', this.resize);
    }
    */

    componentDidMount() {
        this.update();
    }

    render() {
        console.log('QAQ', this.state.tags_curr);
        const { classes } = this.props;

        return (
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <AppBar position="static">
                    <Toolbar>
                        <IconButton
                            edge="start"
                            className={classes.menuButton}
                            color="inherit"
                            aria-label="open drawer"
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
                                        <Chip variant="outlined" label={option} {...getTagProps({ index })} />
                                    ))
                                }
                                renderInput={params => (
                                    <TextField {...params} fullWidth />
                                )}
                                onChange={ (e, value) => this.set_tags(value) }
                                renderOption={option => <Typography noWrap>{option}</Typography>}
                                value={this.state.tags_curr}
                            />
                        </div>
                    </Toolbar>
                </AppBar>


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
